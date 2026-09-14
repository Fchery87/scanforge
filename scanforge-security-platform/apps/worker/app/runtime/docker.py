from __future__ import annotations

import re
import shutil
import subprocess
import time
from uuid import uuid4

from app.runtime.containment import kill_process_tree, popen_scanner_process
from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult, bounded_text

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
        started = time.monotonic()
        container_name = self.new_container_name()
        process = popen_scanner_process(
            self.build_command(request, container_name),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={"PATH": "/usr/bin:/bin"},
        )
        try:
            stdout, stderr = process.communicate(timeout=request.timeout_seconds)
        except subprocess.TimeoutExpired:
            # Kill the CLI process group (it may have spawned children), then
            # force-kill the named container in case the daemon still runs it.
            kill_process_tree(process)
            stdout, stderr = process.communicate()
            self._force_container_kill(container_name)
            return ScanRuntimeResult(
                exit_code=124,
                stdout=bounded_text(stdout, request.output_limit_bytes),
                stderr=bounded_text(stderr, request.output_limit_bytes),
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
                container_name=container_name,
            )
        return ScanRuntimeResult(
            exit_code=process.returncode,
            stdout=bounded_text(stdout, request.output_limit_bytes),
            stderr=bounded_text(stderr, request.output_limit_bytes),
            duration_ms=int((time.monotonic() - started) * 1000),
            container_name=container_name,
        )
