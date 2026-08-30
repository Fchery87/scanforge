from pathlib import Path
from unittest.mock import patch

import pytest

from app.runtime.docker import DockerScanRuntime
from app.runtime.models import ScanRuntimeRequest

IMAGE = "registry.example/scanner@sha256:" + "a" * 64


def make_request(tmp_path: Path, **overrides) -> ScanRuntimeRequest:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    values = {
        "executable": "python",
        "arguments": ("/workspace/source/fixture.py",),
        "source_directory": source,
        "output_directory": output,
        "timeout_seconds": 1,
        "process_limit": 8,
        "memory_limit_mb": 128,
        "disk_limit_mb": 16,
        "output_limit_bytes": 256,
    }
    values.update(overrides)
    return ScanRuntimeRequest(**values)


def runtime() -> DockerScanRuntime:
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        return DockerScanRuntime(IMAGE)


def test_hostile_runtime_command_contains_fork_disk_network_and_symlink_boundaries(tmp_path):
    command = runtime().build_command(make_request(tmp_path))

    assert command[command.index("--pids-limit") + 1] == "8"
    assert command[command.index("--memory") + 1] == "128m"
    assert command[command.index("--network=none")] == "--network=none"
    assert "noexec" in command[command.index("--tmpfs") + 1]
    assert "size=16m" in command[command.index("--tmpfs") + 1]
    source_mount = command[command.index("--mount") + 1]
    assert source_mount.endswith(",readonly")
    assert "/workspace/source" in source_mount


def test_runtime_timeout_is_reported_and_output_is_bounded(tmp_path):
    completed = __import__("subprocess").CompletedProcess(
        args=[],
        returncode=1,
        stdout="x" * 1000,
        stderr="y" * 1000,
    )
    with patch("app.runtime.docker.subprocess.run", return_value=completed):
        result = runtime().run(make_request(tmp_path))

    assert len(result.stdout.encode()) <= 256
    assert len(result.stderr.encode()) <= 256


def test_runtime_rejects_outbound_network_request(tmp_path):
    with pytest.raises(ValueError, match="network access"):
        runtime().build_command(make_request(tmp_path, network_enabled=True))
