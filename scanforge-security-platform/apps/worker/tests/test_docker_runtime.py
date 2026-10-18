import subprocess
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

    assert command[:3] == ["docker", "run", "--rm"]
    assert command[command.index("--name") + 1].startswith("scanforge-scan-")
    assert command[command.index("--env") + 1] == "HOME=/tmp"
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


def test_docker_runtime_accepts_local_image_id_and_reports_its_digest(tmp_path):
    image_id = "sha256:" + "c" * 64
    scan_request = request(tmp_path)
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime(image_id)

    with patch("app.runtime.docker.popen_scanner_process") as popen, patch(
        "app.runtime.docker.communicate_bounded",
        return_value=("", "", False, False, False),
    ):
        popen.return_value.returncode = 0
        result = runtime.run(scan_request)

    assert result.exit_code == 0
    assert result.image_digest == image_id
    assert image_id in runtime.build_command(scan_request)


def test_docker_runtime_reads_image_metadata_offline_with_container_limits():
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime("registry.example/scanner@sha256:" + "d" * 64)
    completed = subprocess.CompletedProcess([], 0, stdout='{"scanners": {}}', stderr="")
    with patch("app.runtime.docker.subprocess.run", return_value=completed) as run:
        assert runtime.read_image_file("/opt/scanner-manifest.json") == '{"scanners": {}}'

    command = run.call_args.args[0]
    assert "--network=none" in command
    assert "--read-only" in command
    assert command[-2:] == ["cat", "/opt/scanner-manifest.json"]
    assert "--memory" in command
    assert "--pids-limit" in command

    with pytest.raises(ValueError, match="normalized path"):
        runtime.read_image_file("/opt/../etc/passwd")


def test_docker_runtime_rejects_network_access(tmp_path):
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime("registry.example/scanner@sha256:" + "a" * 64)

    scan_request = request(tmp_path)
    object.__setattr__(scan_request, "network_enabled", True)
    with pytest.raises(ValueError, match="network access"):
        runtime.build_command(scan_request)
