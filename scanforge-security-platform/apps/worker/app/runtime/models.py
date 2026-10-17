from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import threading
from typing import Any, Callable, Protocol


class ActiveExecutionHandle:
    """Thread-safe handle allowing the orchestrator to cancel an active process or container."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._canceled = threading.Event()
        self._process: subprocess.Popen | None = None
        self._container_name: str = ""
        self._container_kill_callback: Callable[[str], None] | None = None

    @property
    def is_canceled(self) -> bool:
        return self._canceled.is_set()

    @property
    def container_name(self) -> str:
        with self._lock:
            return self._container_name

    def bind(
        self,
        process: subprocess.Popen,
        *,
        container_name: str = "",
        container_kill_callback: Callable[[str], None] | None = None,
    ) -> None:
        with self._lock:
            self._process = process
            self._container_name = container_name
            self._container_kill_callback = container_kill_callback
            already_canceled = self._canceled.is_set()
        if already_canceled:
            self.cancel()

    def cancel(self) -> None:
        from app.runtime.containment import kill_process_tree

        self._canceled.set()
        with self._lock:
            proc = self._process
            container = self._container_name
            kill_cb = self._container_kill_callback
        if proc is not None:
            kill_process_tree(proc)
        if container and kill_cb is not None:
            kill_cb(container)


@dataclass(frozen=True)
class ScanRuntimeRequest:
    executable: str
    arguments: tuple[str, ...]
    source_directory: Path
    output_directory: Path
    timeout_seconds: int = 600
    cpu_limit: float = 1.0
    memory_limit_mb: int = 1024
    process_limit: int = 64
    disk_limit_mb: int = 1024
    output_limit_bytes: int = 50 * 1024 * 1024
    network_enabled: bool = False
    execution_handle: ActiveExecutionHandle | None = field(default=None, compare=False)


@dataclass(frozen=True)
class ScanRuntimeResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    canceled: bool = False
    output_truncated: bool = False
    container_name: str = ""


class ScanRuntime(Protocol):
    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult: ...


def bounded_text(value: Any, max_bytes: int) -> str:
    text = value if isinstance(value, str) else str(value or "")
    encoded = text.encode(errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode(errors="ignore")

