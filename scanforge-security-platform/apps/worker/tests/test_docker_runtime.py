from pathlib import Path
from unittest.mock import patch

import pytest

from app.runtime.docker import DockerScanRuntime
from app.runtime.models import ScanRuntimeRequest


def request(tmp_path: Path) -> ScanRuntimeRequest:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    return ScanRuntimeRequest(
        executable="trivy",
        arguments=("fs", "/workspace/source"),
        source_directory=source,
        output_directory=output,
    )


def test_docker_runtime_requires_digest_and_builds_contained_command(tmp_path):
    with pytest.raises(ValueError, match="pinned by digest"):
        DockerScanRuntime("scanner:latest")

    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime("registry.example/scanner@sha256:" + "a" * 64)

    command = runtime.build_command(request(tmp_path))

    assert command[:4] == ["docker", "run", "--rm", "--user"]
    assert "65532:65532" in command
    assert "--read-only" in command
    assert "--network=none" in command
    assert "--cap-drop" in command
    assert "ALL" in command
    assert "--tmpfs" in command
    assert any("noexec" in value and "size=" in value for value in command)
    assert "no-new-privileges:true" in command
    assert "--pids-limit" in command
    assert "--memory" in command
    assert "--cpus" in command
    assert not any("DOCKER" in value or "TOKEN" in value for value in command)
    assert not any("docker.sock" in value for value in command)


def test_docker_runtime_rejects_network_access(tmp_path):
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime("registry.example/scanner@sha256:" + "a" * 64)

    scan_request = request(tmp_path)
    object.__setattr__(scan_request, "network_enabled", True)
    with pytest.raises(ValueError, match="network access"):
        runtime.build_command(scan_request)
