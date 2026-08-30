from __future__ import annotations

import re
import shutil
import subprocess
import time

from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult, bounded_text


class DockerScanRuntime:
    """Execute a scanner in a credential-free, network-isolated container."""

    def __init__(self, image: str, docker_binary: str = "docker") -> None:
        if not image or not re.fullmatch(r".+@sha256:[0-9a-fA-F]{64}", image):
            raise ValueError("scanner image must be pinned by digest")
        if not shutil.which(docker_binary):
            raise RuntimeError("Docker is required for the private-beta scanner runtime")
        self.image = image
        self.docker_binary = docker_binary

    def build_command(self, request: ScanRuntimeRequest) -> list[str]:
        if request.network_enabled:
            raise ValueError("scanner runtime network access is disabled")
        return [
            self.docker_binary,
            "run",
            "--rm",
            "--user",
            "65532:65532",
            "--read-only",
            "--network=none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            str(request.process_limit),
            "--memory",
            f"{request.memory_limit_mb}m",
            "--cpus",
            str(request.cpu_limit),
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={request.disk_limit_mb}m",  # noqa: S108
            "--mount",
            f"type=bind,src={request.source_directory},dst=/workspace/source,readonly",
            "--mount",
            f"type=bind,src={request.output_directory},dst=/workspace/output",
            "--workdir", "/workspace/source",
            self.image,
            request.executable,
            *request.arguments,
        ]

    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603
                self.build_command(request),
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                env={"PATH": "/usr/bin:/bin"},
            )
            return ScanRuntimeResult(
                exit_code=completed.returncode,
                stdout=bounded_text(completed.stdout, request.output_limit_bytes),
                stderr=bounded_text(completed.stderr, request.output_limit_bytes),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except subprocess.TimeoutExpired as exc:
            return ScanRuntimeResult(
                exit_code=124,
                stdout=bounded_text(exc.stdout, request.output_limit_bytes),
                stderr=bounded_text(exc.stderr, request.output_limit_bytes),
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
