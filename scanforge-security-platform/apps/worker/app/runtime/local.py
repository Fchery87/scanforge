from __future__ import annotations

import subprocess
import time

from app.runtime.containment import kill_process_tree, popen_scanner_process
from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult, bounded_text


class LocalScanRuntime:
    """Test/development runtime. Private beta must use DockerScanRuntime."""

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
        try:
            stdout, stderr = process.communicate(timeout=request.timeout_seconds)
        except subprocess.TimeoutExpired:
            # Kill the entire process group so scanner-spawned children cannot
            # survive the deadline as orphans.
            kill_process_tree(process)
            stdout, stderr = process.communicate()
            return ScanRuntimeResult(
                exit_code=124,
                stdout=bounded_text(stdout, request.output_limit_bytes),
                stderr=bounded_text(stderr, request.output_limit_bytes),
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
        return ScanRuntimeResult(
            exit_code=process.returncode,
            stdout=bounded_text(stdout, request.output_limit_bytes),
            stderr=bounded_text(stderr, request.output_limit_bytes),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
