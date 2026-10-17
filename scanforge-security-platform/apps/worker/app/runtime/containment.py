"""Process-group containment and streaming bounded output collection for scanner subprocesses.

A timeout or cancellation must kill the whole scanner process tree, not only the
direct child. Scanners are therefore started as their own POSIX session/process
group, and a deadline expiry or cancellation SIGKILLs the entire group so spawned
grandchildren cannot outlive the kill.
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from app.runtime.models import ActiveExecutionHandle

POSIX = os.name == "posix"
_READ_CHUNK_BYTES = 16 * 1024


def popen_scanner_process(command: list[str], **kwargs: object) -> subprocess.Popen:
    """Start a scanner as the leader of its own process group on POSIX."""
    if POSIX:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)  # noqa: S603


def kill_process_tree(process: subprocess.Popen) -> None:
    """SIGKILL the scanner's whole process group, then the direct child."""
    if POSIX:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        process.kill()
    except OSError:
        pass


class _BoundedStreamReader:
    """Reads a stream on a background thread while retaining at most max_bytes in memory."""

    def __init__(self, stream: IO[str] | IO[bytes] | None, max_bytes: int) -> None:
        self.stream = stream
        self.max_bytes = max(0, max_bytes)
        self.chunks: list[bytes] = []
        self.captured_bytes = 0
        self.truncated = False
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    def _drain(self) -> None:
        if self.stream is None:
            return
        try:
            while True:
                chunk = self.stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                encoded = chunk.encode("utf-8", errors="replace") if isinstance(chunk, str) else bytes(chunk)
                remaining = self.max_bytes - self.captured_bytes
                if remaining > 0:
                    if len(encoded) <= remaining:
                        self.chunks.append(encoded)
                        self.captured_bytes += len(encoded)
                    else:
                        self.chunks.append(encoded[:remaining])
                        self.captured_bytes += remaining
                        self.truncated = True
                else:
                    self.truncated = True
        except (OSError, ValueError):
            return
        finally:
            try:
                self.stream.close()
            except OSError:
                pass

    def finish(self, join_timeout: float = 2.0) -> tuple[str, bool]:
        self._thread.join(timeout=join_timeout)
        return b"".join(self.chunks).decode("utf-8", errors="ignore"), self.truncated


def communicate_bounded(
    process: subprocess.Popen,
    *,
    timeout_seconds: float,
    output_limit_bytes: int,
    execution_handle: ActiveExecutionHandle | None = None,
) -> tuple[str, str, bool, bool, bool]:
    """Stream stdout/stderr with bounded memory, supporting timeout and immediate cancellation.

    Returns (stdout, stderr, timed_out, canceled, output_truncated).
    """
    stdout_reader = _BoundedStreamReader(process.stdout, output_limit_bytes)
    stderr_reader = _BoundedStreamReader(process.stderr, output_limit_bytes)
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    canceled = False

    while True:
        if execution_handle is not None and execution_handle.is_canceled:
            canceled = True
            kill_process_tree(process)
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            kill_process_tree(process)
            break
        try:
            process.wait(timeout=min(0.05, remaining))
            break
        except subprocess.TimeoutExpired:
            continue

    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        kill_process_tree(process)

    stdout_text, out_trunc = stdout_reader.finish()
    stderr_text, err_trunc = stderr_reader.finish()
    if execution_handle is not None and execution_handle.is_canceled:
        canceled = True
    return stdout_text, stderr_text, timed_out, canceled, (out_trunc or err_trunc)

