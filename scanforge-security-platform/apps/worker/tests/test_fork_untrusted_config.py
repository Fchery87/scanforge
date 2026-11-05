"""#46: fork PR heads never get their own scanner configuration applied."""
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_clone_isolation import _git, _stage, hostile_fixture  # noqa: F401

from app.security.untrusted_config import UNTRUSTED_SCANNER_CONFIG_NAMES, remove_untrusted_scanner_config

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def test_removes_scanner_config_files_at_any_depth_and_keeps_source(tmp_path):
    (tmp_path / "pkg" / "deep").mkdir(parents=True)
    for rel in (".checkov.yaml", ".gitleaks.toml", "pkg/trivy.yaml", "pkg/deep/.trivyignore", "osv-scanner.toml"):
        (tmp_path / rel).write_text("x")
    (tmp_path / "app.py").write_text("print(1)\n")
    (tmp_path / "pkg" / "main.py").write_text("print(2)\n")

    removed = remove_untrusted_scanner_config(tmp_path)

    assert sorted(removed) == [".checkov.yaml", ".gitleaks.toml", "osv-scanner.toml", "pkg/deep/.trivyignore", "pkg/trivy.yaml"]
    assert (tmp_path / "app.py").read_text() == "print(1)\n"
    assert (tmp_path / "pkg" / "main.py").exists()
    assert not any(p.name in UNTRUSTED_SCANNER_CONFIG_NAMES for p in tmp_path.rglob("*"))


def test_symlinked_config_is_removed_without_following_it(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitleaks.toml").symlink_to(outside)

    remove_untrusted_scanner_config(repo)

    assert not (repo / ".gitleaks.toml").is_symlink()
    assert outside.read_text() == "keep"


def _commit_config(source: Path) -> str:
    (source / ".checkov.yaml").write_text("external-checks-dir:\n  - evil\n")
    (source / ".gitleaks.toml").write_text("[allowlist]\npaths = ['.*']\n")
    _git(source, "add", ".")
    _git(source, "commit", "-q", "-m", "scanner config")
    return _git(source, "rev-parse", "HEAD")


@pytest.mark.asyncio
async def test_fork_head_is_acquired_without_its_scanner_configuration(hostile_fixture):  # noqa: F811
    source, _sha, _marker = hostile_fixture
    sha = _commit_config(source)
    stage = _stage(source.resolve().as_uri())
    repo_dir = await stage.prepare_repository(
        SimpleNamespace(
            scan_id="f1", attempt_id="a1", repository_id="r1", commit_sha=sha, branch=None, head_is_fork=True
        )
    )
    try:
        assert (repo_dir / "a.txt").exists()
        assert not (repo_dir / ".checkov.yaml").exists()
        assert not (repo_dir / ".gitleaks.toml").exists()
    finally:
        shutil.rmtree(repo_dir.parent, ignore_errors=True)


@pytest.mark.asyncio
async def test_non_fork_head_keeps_the_acquired_tree_unchanged(hostile_fixture):  # noqa: F811
    source, _sha, _marker = hostile_fixture
    sha = _commit_config(source)
    stage = _stage(source.resolve().as_uri())
    repo_dir = await stage.prepare_repository(
        SimpleNamespace(
            scan_id="f2", attempt_id="a1", repository_id="r1", commit_sha=sha, branch=None, head_is_fork=False
        )
    )
    try:
        assert (repo_dir / ".checkov.yaml").exists()
    finally:
        shutil.rmtree(repo_dir.parent, ignore_errors=True)
