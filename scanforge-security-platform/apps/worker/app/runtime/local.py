from __future__ import annotations

import subprocess
import time

from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult, bounded_text


class LocalScanRuntime:
    """Test/development runtime. Private beta must use DockerScanRuntime."""

    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603
                [request.executable, *request.arguments],
                cwd=request.source_directory,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                env={},
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
