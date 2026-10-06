from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


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


@dataclass(frozen=True)
class ScanRuntimeResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


class ScanRuntime(Protocol):
    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult: ...


def bounded_text(value: Any, max_bytes: int) -> str:
    text = value if isinstance(value, str) else str(value or "")
    encoded = text.encode(errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode(errors="ignore")
