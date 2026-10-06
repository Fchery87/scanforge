import subprocess
from types import SimpleNamespace

import pytest

from app.services.scan_pipeline.execution import ScanExecutionStage


def git(path, *args):
    result = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.asyncio
async def test_diff_uses_recorded_base_head_and_preserves_changed_filenames(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "fixture@example.test")
    git(tmp_path, "config", "user.name", "Fixture")
    (tmp_path / "base.txt").write_text("base")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "first.txt").write_text("first")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "first")
    (tmp_path / "line\nbreak.txt").write_text("second")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "second")
    head = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "later.txt").write_text("unrelated")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "later")
    stage = ScanExecutionStage(SimpleNamespace(), "https://api.example", "credential", runtime=SimpleNamespace())
    changed = await stage.collect_changed_files(tmp_path, base_sha=base, head_sha=head)
    assert changed == ["first.txt", "line\nbreak.txt"]


@pytest.mark.asyncio
async def test_missing_or_invalid_diff_context_fails_explicitly(tmp_path):
    stage = ScanExecutionStage(SimpleNamespace(), "https://api.example", "credential", runtime=SimpleNamespace())
    with pytest.raises(RuntimeError, match="commit"):
        await stage.collect_changed_files(tmp_path)
    with pytest.raises(RuntimeError, match="commit"):
        await stage.collect_changed_files(tmp_path, base_sha="--help", head_sha="a" * 40)


@pytest.mark.asyncio
async def test_cancel_terminates_git_process_before_return(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    started = asyncio.Event()
    blocked = asyncio.Event()
    process = SimpleNamespace(returncode=None, kill=lambda: setattr(process, "returncode", -9), wait=AsyncMock())
    async def communicate():
        started.set()
        await blocked.wait()
    process.communicate = communicate
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    task = asyncio.create_task(ScanExecutionStage._run_git_process(["git", "fetch"]))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.returncode == -9
    process.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkout_fetches_and_scans_recorded_commit_not_current_branch(monkeypatch, tmp_path):
    import asyncio
    import shutil
    from unittest.mock import AsyncMock
    from app.services.scan_pipeline.context import ScanContext
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-b", "main")
    git(origin, "config", "user.email", "fixture@example.test")
    git(origin, "config", "user.name", "Fixture")
    (origin / "recorded.txt").write_text("recorded")
    git(origin, "add", ".")
    git(origin, "commit", "-m", "recorded")
    recorded = git(origin, "rev-parse", "HEAD")
    (origin / "later.txt").write_text("later")
    git(origin, "add", ".")
    git(origin, "commit", "-m", "later")
    spawn = asyncio.create_subprocess_exec
    async def local_clone(*args, **kwargs):
        args = tuple(str(origin) if value == "https://github.com/fixture/repo.git" else value for value in args)
        return await spawn(*args, **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", local_clone)
    stage = ScanExecutionStage(SimpleNamespace(), "https://api.example", "credential", runtime=SimpleNamespace())
    stage._get_clone_url = AsyncMock(return_value=("https://github.com/fixture/repo.git", "Authorization: Basic fixture"))
    context = ScanContext("scan", "org", "repo", "project", "main", recorded, "job")
    checkout = await stage.prepare_repository(context)
    try:
        assert git(checkout, "rev-parse", "HEAD") == recorded
        assert (checkout / "recorded.txt").read_text() == "recorded"
        assert not (checkout / "later.txt").exists()
    finally:
        shutil.rmtree(checkout)
