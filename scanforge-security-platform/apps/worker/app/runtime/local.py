from __future__ import annotations

import subprocess
import time

from app.runtime.containment import communicate_bounded, popen_scanner_process
from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult


class LocalScanRuntime:
    """Test/development runtime. Customer environments must use DockerScanRuntime."""

    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult:
        started = time.monotonic()
        process = popen_scanner_process(
            [request.executable, *request.arguments],
            cwd=request.source_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={},
        )
        if request.execution_handle is not None:
            request.execution_handle.bind(process)
        stdout, stderr, timed_out, canceled, truncated = communicate_bounded(
            process,
            timeout_seconds=request.timeout_seconds,
            output_limit_bytes=request.output_limit_bytes,
            execution_handle=request.execution_handle,
        )
        if timed_out or canceled:
            return ScanRuntimeResult(
                exit_code=124 if timed_out else 130,
                stdout=stdout,
                stderr=stderr,
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=timed_out,
                canceled=canceled,
                output_truncated=truncated,
            )
        return ScanRuntimeResult(
            exit_code=process.returncode if process.returncode is not None else 1,
            stdout=stdout,
            stderr=stderr,
            duration_ms=int((time.monotonic() - started) * 1000),
            output_truncated=truncated,
        )

