"""R08 evidence: scanner subprocess environment containment.

Every subprocess the worker spawns for scanning or cloning must receive an
allowlisted environment. API database URLs, worker credentials, webhook
secrets, and object-storage keys must never reach a scanner or git subprocess.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime.local import LocalScanRuntime
from app.runtime.models import ScanRuntimeRequest
from app.scanners.registry import SCANNER_REGISTRY
from app.scanners.trivy import TrivyAdapter

FORBIDDEN_ENV = {
    "DATABASE_URL": "postgresql://api:r08-api-secret@db:5432/scanforge",
    "WORKER_CREDENTIAL": "r08-worker-credential-value",
    "GITHUB_WEBHOOK_SECRET": "r08-whsec-value",
    "R2_ACCESS_KEY_ID": "r08-access-key",
    "R2_SECRET_ACCESS_KEY": "r08-secret-key",
    "OPENAI_API_KEY": "sk-r08-not-for-scanners",
    "REDIS_URL": "redis://:r08-redis-password@redis:6379/0",
}

ALLOWED_ENV_KEYS = frozenset(
    {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE"}
)

GIT_AUTH_KEYS = {"GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0"}


def _seed_forbidden_env(monkeypatch) -> None:
    for key, value in FORBIDDEN_ENV.items():
        monkeypatch.setenv(key, value)


def _recording_run(monkeypatch, captured: list, stdout: str = "", returncode: int = 0):
    def fake_run(cmd, *args, **kwargs):
        captured.append(kwargs.get("env"))
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)


def _assert_env_contained(env, label: str) -> None:
    assert env is not None, f"{label} must pass an explicit env dict"
    extra = set(env) - ALLOWED_ENV_KEYS
    assert not extra, f"{label} environment leaks non-allowlisted keys: {sorted(extra)}"
    for key in FORBIDDEN_ENV:
        assert key not in env, f"{label} environment leaks forbidden key {key}"
    assert FORBIDDEN_ENV["WORKER_CREDENTIAL"] not in json.dumps(env, default=str)


def test_local_runtime_passes_empty_environment_to_real_scanner_process(tmp_path):
    runtime = LocalScanRuntime()
    request = ScanRuntimeRequest(
        executable="/usr/bin/env",
        arguments=(),
        source_directory=tmp_path,
        output_directory=tmp_path,
        timeout_seconds=10,
    )
    result = runtime.run(request)
    assert result.exit_code == 0
    assert result.stdout.strip() == "", f"scanner process saw environment: {result.stdout!r}"


def test_docker_runtime_cli_environment_is_minimal(monkeypatch, tmp_path):
    _seed_forbidden_env(monkeypatch)
    monkeypatch.setattr("app.runtime.docker.shutil.which", lambda _name: "/usr/bin/docker")
    from app.runtime.docker import DockerScanRuntime

    runtime = DockerScanRuntime(image="ghcr.io/test/scanner@sha256:" + "a" * 64)
    captured: list = []
    _recording_run(monkeypatch, captured)
    request = ScanRuntimeRequest(
        executable="trivy",
        arguments=("fs", "."),
        source_directory=tmp_path,
        output_directory=tmp_path,
        timeout_seconds=10,
    )
    runtime.run(request)
    env = captured[0]
    assert env is not None
    assert set(env) <= ALLOWED_ENV_KEYS, f"docker CLI env not minimal: {sorted(env)}"


@pytest.mark.asyncio
async def test_git_clone_environment_is_allowlisted(monkeypatch):
    _seed_forbidden_env(monkeypatch)
    captured: list = []
    _recording_run(monkeypatch, captured)

    from app.services.scan_pipeline.execution import ScanExecutionStage

    stage = ScanExecutionStage(
        r2=AsyncMock(),
        api_base_url="http://api.test",
        worker_credential=FORBIDDEN_ENV["WORKER_CREDENTIAL"],
    )
    monkeypatch.setattr(
        stage,
        "_get_clone_url",
        AsyncMock(return_value=("https://github.com/org/repo.git", "Basic r08-auth-header")),
    )
    repo_dir = None
    try:
        repo_dir = await stage.prepare_repository(
            SimpleNamespace(repository_id="repo-1", branch=None)
        )
    finally:
        if repo_dir is not None:
            shutil.rmtree(repo_dir, ignore_errors=True)

    env = captured[0]
    _assert_env_contained(env, "git clone")
    assert env["GIT_CONFIG_VALUE_0"] == "Basic r08-auth-header"
    assert env.get("GIT_CONFIG_COUNT") == "1"


def test_scanner_version_probe_environment_is_allowlisted(monkeypatch):
    _seed_forbidden_env(monkeypatch)
    failures: list[str] = []
    for name, registration in SCANNER_REGISTRY.items():
        adapter = registration.adapter_factory()
        captured: list = []
        _recording_run(monkeypatch, captured)
        adapter.get_version()
        try:
            _assert_env_contained(captured[-1] if captured else None, f"{name} get_version")
        except AssertionError as exc:
            failures.append(str(exc))
    assert not failures, "\n".join(failures)


def test_trivy_scan_environment_is_allowlisted(monkeypatch, tmp_path):
    _seed_forbidden_env(monkeypatch)
    captured: list = []

    def fake_run(cmd, *args, **kwargs):
        captured.append(kwargs.get("env"))
        (tmp_path / "trivy-results.json").write_text('{"Results": []}')
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = TrivyAdapter().run(tmp_path)
    assert result.success is True
    assert captured, "trivy run must invoke a subprocess"
    for i, env in enumerate(captured):
        _assert_env_contained(env, f"trivy run subprocess #{i}")
