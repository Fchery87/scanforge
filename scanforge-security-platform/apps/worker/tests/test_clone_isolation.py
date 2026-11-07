"""P1.2: source acquisition ignores host Git configuration and requires an exact SHA."""
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.security.proc_env import build_git_env
from app.services.scan_pipeline.execution import ScanExecutionStage

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def _pairs(env):
    return {
        env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"]
        for i in range(int(env["GIT_CONFIG_COUNT"]))
    }


def test_git_env_disables_host_configuration(tmp_path):
    env = build_git_env(auth_header="Basic abc", home_dir=tmp_path)
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["HOME"] == str(tmp_path)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_LFS_SKIP_SMUDGE"] == "1"
    pairs = _pairs(env)
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert pairs["core.hooksPath"] == "/dev/null"
    assert pairs["core.fsmonitor"] == "false"
    assert pairs["protocol.allow"] == "never"
    assert pairs["protocol.https.allow"] == "always"
    assert "protocol.file.allow" not in pairs


def test_git_env_allows_file_protocol_only_when_requested(tmp_path):
    env = build_git_env(auth_header="", home_dir=tmp_path, allow_file_protocol=True)
    pairs = _pairs(env)
    assert pairs["protocol.file.allow"] == "always"
    assert "http.extraHeader" not in pairs


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def hostile_fixture(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q")
    _git(source, "config", "user.email", "fixture@example.invalid")
    _git(source, "config", "user.name", "fixture")
    (source / ".gitattributes").write_text("*.txt filter=hostile\n")
    (source / "a.txt").write_text("content\n")
    _git(source, "add", ".")
    _git(source, "commit", "-q", "-m", "fixture")
    sha = _git(source, "rev-parse", "HEAD")

    marker = tmp_path / "host-filter-ran"
    fake_home = tmp_path / "host-home"
    fake_home.mkdir()
    (fake_home / ".gitconfig").write_text(
        # The value must be quoted: an unquoted ';' starts a gitconfig comment
        # and would make the filter inert, so the test could never fail.
        f'[filter "hostile"]\n\tsmudge = "sh -c \'touch {marker}; cat\'"\n'
    )
    # Prove the fixture itself is live under the host configuration.
    control = tmp_path / "control"
    control.mkdir()
    _git(control, "init", "-q")
    (control / ".gitattributes").write_text("*.txt filter=hostile\n")
    (control / "b.txt").write_text("x\n")
    host_env = {
        "PATH": os.environ["PATH"],
        "HOME": str(fake_home),
        "GIT_AUTHOR_NAME": "f", "GIT_AUTHOR_EMAIL": "f@example.invalid",
        "GIT_COMMITTER_NAME": "f", "GIT_COMMITTER_EMAIL": "f@example.invalid",
    }
    for args in (["add", "."], ["commit", "-q", "-m", "c"]):
        subprocess.run(["git", "-C", str(control), *args], check=True, capture_output=True, env=host_env)
    (control / "b.txt").unlink()
    subprocess.run(["git", "-C", str(control), "checkout", "--", "b.txt"], check=True, capture_output=True, env=host_env)
    assert marker.exists(), "fixture filter is inert; the isolation test would be vacuous"
    marker.unlink()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SCANFORGE_ALLOW_LOCAL_GIT_FIXTURES", "1")
    monkeypatch.setenv("WORKER_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    return source, sha, marker


def _stage(clone_url: str) -> ScanExecutionStage:
    stage = ScanExecutionStage(
        r2=AsyncMock(), api_base_url="http://api.test", worker_credential="w", runtime=object()
    )
    stage._get_clone_url = AsyncMock(return_value=(clone_url, ""))
    return stage


@pytest.mark.asyncio
async def test_host_git_filter_does_not_run_on_checkout(hostile_fixture):
    source, sha, marker = hostile_fixture
    stage = _stage(source.resolve().as_uri())
    repo_dir = await stage.prepare_repository(
        SimpleNamespace(scan_id="s1", attempt_id="a1", repository_id="r1", commit_sha=sha, branch=None)
    )
    try:
        assert (repo_dir / "a.txt").read_text() == "content\n"
        assert not marker.exists(), "host-defined Git filter executed during checkout"
    finally:
        shutil.rmtree(repo_dir.parent, ignore_errors=True)


@pytest.mark.asyncio
async def test_missing_commit_sha_is_refused(hostile_fixture):
    source, _sha, _marker = hostile_fixture
    stage = _stage(source.resolve().as_uri())
    with pytest.raises(RuntimeError, match="exact commit SHA is required"):
        await stage.prepare_repository(
            SimpleNamespace(scan_id="s2", attempt_id="a1", repository_id="r1", commit_sha=None, branch="main")
        )


@pytest.mark.asyncio
async def test_missing_commit_sha_fails_before_any_network_activity(hostile_fixture, monkeypatch):
    source, _sha, _marker = hostile_fixture
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or pytest.fail("git ran"))
    stage = _stage(source.resolve().as_uri())
    with pytest.raises(RuntimeError, match="exact commit SHA is required"):
        await stage.prepare_repository(
            SimpleNamespace(scan_id="s3", attempt_id="a1", repository_id="r1", commit_sha="  ", branch="main")
        )
    assert calls == []


@pytest.mark.asyncio
async def test_file_transport_rejected_for_customer_environment(hostile_fixture, monkeypatch):
    source, sha, _marker = hostile_fixture
    monkeypatch.setenv("APP_ENV", "production")
    stage = _stage(source.resolve().as_uri())
    with pytest.raises(RuntimeError, match="verified github.com origin"):
        await stage.prepare_repository(
            SimpleNamespace(scan_id="s4", attempt_id="a1", repository_id="r1", commit_sha=sha, branch=None)
        )


@pytest.mark.asyncio
async def test_non_https_transport_rejected(hostile_fixture):
    _source, sha, _marker = hostile_fixture
    stage = _stage("ssh://git@github.com/org/repo.git")
    with pytest.raises(RuntimeError, match="verified github.com origin"):
        await stage.prepare_repository(
            SimpleNamespace(scan_id="s5", attempt_id="a1", repository_id="r1", commit_sha=sha, branch=None)
        )
