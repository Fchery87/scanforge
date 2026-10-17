from __future__ import annotations

import re
import shutil
import subprocess
import time
from uuid import uuid4

from app.runtime.containment import communicate_bounded, popen_scanner_process
from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult

# Proposed cleanup budget from the readiness plan: kill the daemon-owned
# container within 30 seconds of the configured deadline.
CONTAINER_KILL_BUDGET_SECONDS = 30


class DockerScanRuntime:
    """Execute a scanner in a credential-free, network-isolated container."""

    def __init__(self, image: str, docker_binary: str = "docker") -> None:
        if not image or not re.fullmatch(r".+@sha256:[0-9a-fA-F]{64}", image):
            raise ValueError("scanner image must be pinned by digest")
        if not shutil.which(docker_binary):
            raise RuntimeError("Docker is required for the private-beta scanner runtime")
        self.image = image
        self.docker_binary = docker_binary

    @staticmethod
    def new_container_name() -> str:
        """Explicit container identity so cleanup never depends on CLI liveness."""
        return f"scanforge-scan-{uuid4().hex[:12]}"

    def build_command(
        self,
        request: ScanRuntimeRequest,
        container_name: str | None = None,
    ) -> list[str]:
        if request.network_enabled:
            raise ValueError("scanner runtime network access is disabled")
        return [
            self.docker_binary,
            "run",
            "--rm",
            "--name",
            container_name or self.new_container_name(),
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

    def _force_container_kill(self, container_name: str) -> None:
        """SIGKILL of the CLI cannot stop a daemon-owned container; kill by name."""
        try:
            subprocess.run(  # noqa: S603
                [self.docker_binary, "kill", container_name],
                capture_output=True,
                text=True,
                timeout=CONTAINER_KILL_BUDGET_SECONDS,
                env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.SubprocessError):
            return

    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult:
        from app.runtime.base import prepare_scanner_output_directory

        prepare_scanner_output_directory(request.output_directory)
        started = time.monotonic()
        container_name = self.new_container_name()
        process = popen_scanner_process(
            self.build_command(request, container_name),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": "/usr/bin:/bin"},
        )
        if request.execution_handle is not None:
            request.execution_handle.bind(
                process,
                container_name=container_name,
                container_kill_callback=self._force_container_kill,
            )
        stdout, stderr, timed_out, canceled, truncated = communicate_bounded(
            process,
            timeout_seconds=request.timeout_seconds,
            output_limit_bytes=request.output_limit_bytes,
            execution_handle=request.execution_handle,
        )
        if timed_out or canceled:
            self._force_container_kill(container_name)
            return ScanRuntimeResult(
                exit_code=124 if timed_out else 130,
                stdout=stdout,
                stderr=stderr,
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=timed_out,
                canceled=canceled,
                output_truncated=truncated,
                container_name=container_name,
            )
        return ScanRuntimeResult(
            exit_code=process.returncode if process.returncode is not None else 1,
            stdout=stdout,
            stderr=stderr,
            duration_ms=int((time.monotonic() - started) * 1000),
            output_truncated=truncated,
            container_name=container_name,
        )

