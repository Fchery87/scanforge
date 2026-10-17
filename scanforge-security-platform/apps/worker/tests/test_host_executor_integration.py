from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import threading
import time
from unittest.mock import patch

import pytest

from app.runtime.base import (
    CUSTOMER_FACING_ENVIRONMENTS,
    build_scan_runtime,
    prepare_isolated_scan_workspace,
    prepare_scanner_output_directory,
    verify_host_coordinator_prerequisites,
)
from app.runtime.docker import DockerScanRuntime
from app.runtime.local import LocalScanRuntime
from app.runtime.models import ActiveExecutionHandle, ScanRuntimeRequest
from app.worker.main import Worker

PINNED_IMAGE = "registry.example/scanforge-scanners@sha256:" + "b" * 64


@pytest.mark.parametrize("env_name", sorted(CUSTOMER_FACING_ENVIRONMENTS))
def test_customer_environments_never_fall_back_to_local_runtime(monkeypatch, env_name):
    monkeypatch.setenv("APP_ENV", env_name)
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.delenv("SCANNER_IMAGE", raising=False)

    with pytest.raises(ValueError, match="pinned by digest"):
        build_scan_runtime()

    monkeypatch.setenv("SCANNER_IMAGE", PINNED_IMAGE)
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"), patch(
        "app.runtime.base.shutil.which", return_value="/usr/bin/git"
    ):
        runtime = build_scan_runtime()
    assert isinstance(runtime, DockerScanRuntime)


def test_missing_git_or_docker_fails_host_coordinator_prerequisites(monkeypatch, tmp_path):
    ws_root = tmp_path / "workspaces"
    monkeypatch.setenv("APP_ENV", "private-beta")
    monkeypatch.setenv("WORKER_WORKSPACE_ROOT", str(ws_root))
    monkeypatch.setenv("SCANNER_IMAGE", PINNED_IMAGE)

    with patch("app.runtime.base.shutil.which", side_effect=lambda cmd: None if cmd == "git" else "/usr/bin/docker"):
        with pytest.raises(RuntimeError, match="git is required"):
            verify_host_coordinator_prerequisites()

    with patch("app.runtime.base.shutil.which", side_effect=lambda cmd: "/usr/bin/git" if cmd == "git" else None):
        with pytest.raises(RuntimeError, match="Docker is required"):
            verify_host_coordinator_prerequisites()


def test_customer_worker_enforces_single_concurrent_scan(monkeypatch):
    monkeypatch.setenv("APP_ENV", "private-beta")
    with pytest.raises(ValueError, match="concurrency must be 1"):
        Worker(concurrency=4)


def test_isolated_workspace_and_output_mount_permissions_for_scanner_uid(tmp_path):
    ws_root = tmp_path / "workspaces"
    source_dir = prepare_isolated_scan_workspace(ws_root, scan_id="scan-123", attempt_id="attempt-1")
    (source_dir / "README.md").write_text("hello")
    from app.runtime.base import make_source_readable_for_scanner

    make_source_readable_for_scanner(source_dir)
    out_dir = prepare_scanner_output_directory(source_dir.parent / "output_trivy")

    # Root workspace is 0o700 (restricted to the coordinator account)
    assert stat.S_IMODE(ws_root.stat().st_mode) == 0o700
    # Scan parent dir allows traversal (0o711) so container UID 65532 can traverse bind mount
    assert stat.S_IMODE(source_dir.parent.stat().st_mode) == 0o711
    # Source dir is readable/traversable (0o755) and files are 0o644
    assert stat.S_IMODE(source_dir.stat().st_mode) == 0o755
    assert stat.S_IMODE((source_dir / "README.md").stat().st_mode) == 0o644
    # Output dir is writable by container UID 65532 (0o1777 sticky world-writable inside 0o700 ws_root)
    assert stat.S_IMODE(out_dir.stat().st_mode) & 0o777 == 0o777


def test_streaming_bounded_stdout_stderr_prevents_unbounded_memory_buffering(tmp_path):
    script = tmp_path / "noisy.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.write('A' * 65536)\n"
        "sys.stdout.flush()\n"
        "sys.stderr.write('B' * 65536)\n"
        "sys.stderr.flush()\n"
    )
    source = tmp_path / "src"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()

    runtime = LocalScanRuntime()
    result = runtime.run(
        ScanRuntimeRequest(
            executable="python3",
            arguments=(str(script),),
            source_directory=source,
            output_directory=output,
            output_limit_bytes=4096,
            timeout_seconds=10,
        )
    )

    assert result.exit_code == 0
    assert len(result.stdout.encode("utf-8")) <= 4096
    assert len(result.stderr.encode("utf-8")) <= 4096
    assert result.output_truncated is True


@pytest.mark.skipif(os.name != "posix", reason="process-group kill requires POSIX")
def test_active_execution_handle_cancels_running_process_tree_immediately(tmp_path):
    pids_file = tmp_path / "pids.txt"
    script = tmp_path / "long_scan.py"
    script.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen(['sleep', '120'])\n"
        "with open(sys.argv[1], 'w') as f:\n"
        "    f.write(str(child.pid))\n"
        "    f.flush()\n"
        "time.sleep(120)\n"
    )
    source = tmp_path / "src"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()

    handle = ActiveExecutionHandle()
    runtime = LocalScanRuntime()

    def trigger_cancel():
        deadline = time.monotonic() + 5.0
        while not pids_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.05)
        handle.cancel()

    canceler = threading.Thread(target=trigger_cancel, daemon=True)
    canceler.start()

    started = time.monotonic()
    result = runtime.run(
        ScanRuntimeRequest(
            executable="python3",
            arguments=(str(script), str(pids_file)),
            source_directory=source,
            output_directory=output,
            timeout_seconds=60,
            execution_handle=handle,
        )
    )
    elapsed = time.monotonic() - started

    assert result.canceled is True
    assert elapsed < 10.0
    child_pid = int(pids_file.read_text().strip())
    # Verify child is dead
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            stat_text = Path(f"/proc/{child_pid}/stat").read_text()
            state = stat_text.rsplit(")", 1)[1].split()[0]
            if state in ("Z", "X"):
                break
        except (FileNotFoundError, ProcessLookupError):
            break
        time.sleep(0.05)
    else:
        pytest.fail(f"Child process {child_pid} survived handle.cancel()")


def test_provision_worker_host_script_verifies_git_docker_and_forbidden_secrets(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "provision_worker_host.sh"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for tool in ("git", "docker"):
        exe = fake_bin / tool
        exe.write_text("#!/usr/bin/env bash\nexit 0\n")
        exe.chmod(0o755)
    ws_root = tmp_path / "ws"
    env = {**os.environ, "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"}
    res = subprocess.run(
        ["bash", str(script), "--verify-only", "--workspace-root", str(ws_root)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert res.returncode == 0
    assert stat.S_IMODE(ws_root.stat().st_mode) == 0o700


def test_live_docker_container_isolation_and_mount_contract(tmp_path):
    """Run a real disposable container against the local Docker daemon to verify
    UID 65532:65532, read-only source, writable output, no network, and no env secrets.
    """
    import shutil

    if not shutil.which("docker"):
        pytest.skip("Docker binary not installed on this host; live container execution unverified locally")

    inspect_proc = subprocess.run(
        ["docker", "image", "inspect", "postgres:16-alpine", "--format", "{{index .RepoDigests 0}}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if inspect_proc.returncode != 0 or "@sha256:" not in inspect_proc.stdout.strip():
        pytest.skip("Local pinned container image not available for live Docker runtime check")

    pinned_image = inspect_proc.stdout.strip()
    ws_root = tmp_path / "ws"
    source_dir = prepare_isolated_scan_workspace(ws_root, scan_id="live-scan", attempt_id="att-1")
    (source_dir / "sample.txt").write_text("immutable-source-content")
    from app.runtime.base import make_source_readable_for_scanner

    make_source_readable_for_scanner(source_dir)
    output_dir = prepare_scanner_output_directory(source_dir.parent / "output")

    runtime = DockerScanRuntime(pinned_image)
    result = runtime.run(
        ScanRuntimeRequest(
            executable="/bin/sh",
            arguments=(
                "-c",
                "id -u && id -g && cat /workspace/source/sample.txt > /workspace/output/report.txt "
                "&& (touch /workspace/source/write_attempt 2>/dev/null && exit 99 || true) "
                "&& env",
            ),
            source_directory=source_dir,
            output_directory=output_dir,
            timeout_seconds=30,
        )
    )

    assert result.exit_code == 0, f"Container failed: stderr={result.stderr}"
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines[0] == "65532"
    assert lines[1] == "65532"
    assert (output_dir / "report.txt").read_text() == "immutable-source-content"
    assert not (source_dir / "write_attempt").exists()
    assert "WORKER_CREDENTIAL" not in result.stdout
    assert "DATABASE_URL" not in result.stdout

