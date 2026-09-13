"""R07 scanner containment: process-tree kill on timeout, artifact path
isolation boundaries, and verifiable workspace cleanup receipts.

Timeout tests spawn real long-running dummy subprocesses and assert that no
process from the spawned tree survives the configured deadline.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.clients.r2 import R2Client
from app.runtime.docker import DockerScanRuntime
from app.runtime.local import LocalScanRuntime
from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult
from app.security.secret_evidence import safe_artifact_key
from app.services.scan_orchestrator import ScanOrchestrator
from app.services.scan_pipeline.context import ScanContext

IMAGE = "registry.example/scanner@sha256:" + "a" * 64


def make_request(tmp_path: Path, **overrides) -> ScanRuntimeRequest:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    values = {
        "executable": "true",
        "arguments": (),
        "source_directory": source,
        "output_directory": output,
        "timeout_seconds": 2,
    }
    values.update(overrides)
    return ScanRuntimeRequest(**values)


def _proc_state(pid: int) -> str | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return None
    return stat.rsplit(")", 1)[1].split()[0]


def _assert_tree_dead(pids: list[int], deadline_seconds: float = 5.0) -> None:
    """Every recorded pid must be gone or a reaped-state zombie by the deadline."""
    deadline = time.monotonic() + deadline_seconds
    remaining = list(pids)
    while remaining and time.monotonic() < deadline:
        remaining = [pid for pid in remaining if _proc_state(pid) not in (None, "Z", "X")]
        if not remaining:
            return
        time.sleep(0.05)
    assert not remaining, f"orphaned scanner processes survived the timeout kill: {remaining}"


DUMMY_SCANNER = """import subprocess, sys, time
child = subprocess.Popen(["sleep", "120"])
grandchild = subprocess.Popen(["sleep", "120"])
with open(sys.argv[1], "w") as handle:
    handle.write(str(child.pid))
    handle.write(" ")
    handle.write(str(grandchild.pid))
time.sleep(120)
"""


@pytest.mark.skipif(os.name != "posix", reason="process-group kill requires POSIX")
def test_local_runtime_timeout_kills_entire_process_tree(tmp_path):
    """A timed-out scanner must leave no children or grandchildren running."""
    pids_file = tmp_path / "child_pids.txt"
    script = tmp_path / "dummy_scanner.py"
    script.write_text(DUMMY_SCANNER)

    runtime = LocalScanRuntime()
    result = runtime.run(
        make_request(
            tmp_path,
            executable="python3",
            arguments=(str(script), str(pids_file)),
            timeout_seconds=2,
        )
    )

    assert result.timed_out is True
    assert result.exit_code == 124
    recorded = [int(value) for value in pids_file.read_text().split()]
    assert len(recorded) == 2, "dummy scanner did not record its process tree"
    _assert_tree_dead(recorded)


FAKE_DOCKER_TEMPLATE = """#!/usr/bin/env bash
echo "$@" >> {log_path}
if [ "$1" = "run" ]; then
  sleep 120 &
  echo $! >> {pids_path}
  exec sleep 120
fi
if [ "$1" = "kill" ]; then
  exit 0
fi
exit 1
"""


@pytest.mark.skipif(os.name != "posix", reason="process-group kill requires POSIX")
def test_docker_runtime_timeout_kills_cli_group_and_issues_container_kill(tmp_path):
    """Timeout must kill the CLI process group and force-kill the named container."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "invocations.log"
    pids_path = tmp_path / "container_pids.txt"
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        FAKE_DOCKER_TEMPLATE.format(log_path=log_path, pids_path=pids_path)
    )
    fake_docker.chmod(0o755)

    runtime = DockerScanRuntime(IMAGE, docker_binary=str(fake_docker))
    result = runtime.run(
        make_request(tmp_path, executable="trivy", arguments=("fs", "/workspace/source"), timeout_seconds=1)
    )

    assert result.timed_out is True
    assert result.exit_code == 124
    assert result.container_name, "timeout must record the container identity for cleanup"

    invocations = log_path.read_text().splitlines()
    run_invocation = next(line for line in invocations if line.startswith("run "))
    assert "--name" in run_invocation
    assert result.container_name in run_invocation
    assert invocations[-1] == f"kill {result.container_name}"

    container_pid = int(pids_path.read_text().strip())
    _assert_tree_dead([container_pid])


def test_docker_runtime_builds_explicit_container_identity(tmp_path):
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime(IMAGE)

    command = runtime.build_command(make_request(tmp_path), container_name="scan-abc123")

    assert command[command.index("--name") + 1] == "scan-abc123"


def test_local_runtime_reports_container_identity_field_shape():
    result = ScanRuntimeResult(exit_code=0, stdout="", stderr="", duration_ms=1)
    assert result.container_name == ""
    assert result.timed_out is False


# ─── Artifact path isolation ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("org", "scan", "scanner", "filename"),
    [
        ("org-1", "scan-1", "trivy", "../escape.json"),
        ("org-1", "scan-1", "trivy", "/etc/passwd"),
        ("org-1", "scan-1", "trivy", "sub/dir.json"),
        ("org-1", "scan-1", "trivy", "back\\slash.json"),
        ("org-1", "scan-1", "trivy", "."),
        ("org-1", "scan-1", "trivy", ".."),
        ("org-1", "scan-1", "trivy", ""),
        ("../other-org", "scan-1", "trivy", "results.json"),
        ("org-1", "../other-scan", "trivy", "results.json"),
        ("org-1", "scan-1", "../trivy", "results.json"),
        ("", "scan-1", "trivy", "results.json"),
        ("org-1", "", "trivy", "results.json"),
    ],
)
def test_safe_artifact_key_rejects_cross_tenant_and_traversal_components(org, scan, scanner, filename):
    with pytest.raises(ValueError):
        safe_artifact_key(org, scan, scanner, filename)


def test_safe_artifact_key_builds_exact_tenant_scoped_key():
    key = safe_artifact_key("org-1", "scan-1", "trivy", "results.json")
    assert key == "scan-artifacts/org-1/scan-1/trivy/results.json"


@pytest.mark.asyncio
async def test_r2_client_refuses_put_when_api_returns_foreign_org_key(tmp_path):
    """A worker must never write to another organization's artifact prefix."""
    artifact = tmp_path / "results.json"
    artifact.write_text("{}")
    client = R2Client("https://api.example", "worker-secret")

    presign_response = Mock()
    presign_response.json.return_value = {
        "key": "scan-artifacts/other-org/other-scan/trivy/results.json",
        "upload_url": "https://storage.example/foreign-key",
    }
    http_client = AsyncMock()
    http_client.post.return_value = presign_response
    http_client.__aenter__.return_value = http_client
    http_client.__aexit__.return_value = False

    with patch("app.clients.r2.httpx.AsyncClient", return_value=http_client), pytest.raises(
        RuntimeError, match="outside the requested tenant scope"
    ):
        await client.upload_file(artifact, "scan-artifacts/org-1/scan-1/trivy/results.json")

    http_client.put.assert_not_called()


# ─── Workspace cleanup receipt ───────────────────────────────────────


def make_orchestrator() -> ScanOrchestrator:
    return ScanOrchestrator(queue=Mock(), r2=Mock(), api_base_url="http://test")


def make_context(repo_path: Path | None) -> ScanContext:
    return ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha=None,
        job_id="job-1",
        repo_path=repo_path,
    )


def test_cleanup_receipt_reports_removed_workspace(tmp_path):
    workspace = tmp_path / "scan_repo_x"
    workspace.mkdir()
    (workspace / "clone.git").touch()

    receipt = make_orchestrator()._cleanup_workspace(make_context(workspace))

    assert not workspace.exists()
    assert receipt["scan_id"] == "scan-1"
    assert receipt["workspace"] == str(workspace)
    assert receipt["removed"] is True
    assert receipt["residual"] is None
    assert receipt["duration_ms"] >= 0


def test_cleanup_receipt_records_residual_when_removal_fails(tmp_path, monkeypatch):
    workspace = tmp_path / "scan_repo_stuck"
    workspace.mkdir()
    monkeypatch.setattr(
        "app.services.scan_orchestrator.shutil.rmtree", lambda *_args, **_kw: None
    )

    context = make_context(workspace)
    receipt = make_orchestrator()._cleanup_workspace(context)

    assert workspace.exists()
    assert receipt["removed"] is False
    assert receipt["residual"] == str(workspace)
    assert context.cleanup_receipt == receipt


def test_cleanup_receipt_without_workspace_reports_nothing_remaining():
    receipt = make_orchestrator()._cleanup_workspace(make_context(None))

    assert receipt["workspace"] is None
    assert receipt["removed"] is True
    assert receipt["residual"] is None
