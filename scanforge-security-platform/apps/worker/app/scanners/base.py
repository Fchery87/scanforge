import json
import os
import stat
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScannerResult:
    scanner_name: str
    success: bool
    raw_output: dict[str, Any] | list[dict[str, Any]]
    artifact_paths: list[Path] = field(default_factory=list)
    version: str = ""
    duration_ms: int = 0
    error: str = ""
    provenance: dict[str, str] = field(default_factory=dict)


class ScannerAdapter(ABC):
    name: str = "base"
    binary_name: str = ""
    binary_env_var: str | None = None
    report_filename: str = ""
    report_from_stdout: bool = False
    retain_report: bool = True
    accepted_exit_codes: frozenset[int] = frozenset({0})
    max_report_bytes: int = 50 * 1024 * 1024

    def __init__(self):
        if self.binary_env_var:
            self.binary_name = os.environ.get(self.binary_env_var, self.binary_name)

    @abstractmethod
    def run(self, repo_path: Path) -> ScannerResult:
        raise NotImplementedError

    def run_contained(self, repo_path: Path, runtime, output_directory: Path) -> ScannerResult:
        from app.runtime.models import ScanRuntimeRequest

        if output_directory.is_symlink() or output_directory.absolute() != output_directory.resolve():
            raise ValueError("scanner output directory cannot be a symlink")
        output_directory.mkdir(parents=True, exist_ok=False)
        request = ScanRuntimeRequest(
            executable=Path(self.binary_name).name,
            arguments=self.runtime_arguments(),
            source_directory=repo_path,
            output_directory=output_directory,
            timeout_seconds=self.runtime_timeout_seconds(),
            output_limit_bytes=self.max_report_bytes,
        )
        completed = runtime.run(request)
        return self.parse_runtime_result(completed, output_directory)

    @abstractmethod
    def runtime_arguments(self) -> tuple[str, ...]:
        raise NotImplementedError

    def runtime_timeout_seconds(self) -> int:
        return 600

    @abstractmethod
    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        raise NotImplementedError

    def _parse_report(self, completed, output_directory: Path, validator: Callable[[Any], bool]) -> ScannerResult:
        failed = ScannerResult(
            scanner_name=self.name,
            success=False,
            raw_output={},
            duration_ms=completed.duration_ms,
            error="Scanner did not produce valid evidence",
        )
        if completed.timed_out or completed.exit_code not in self.accepted_exit_codes:
            failed.error = "Scanner timed out" if completed.timed_out else "Scanner exited unsuccessfully"
            return failed
        path = output_directory / self.report_filename
        try:
            if self.report_from_stdout:
                encoded = completed.stdout.encode()
                if len(encoded) > self.max_report_bytes:
                    return failed
                payload = json.loads(encoded)
            else:
                with open(path, "rb", opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW)) as report:
                    info = os.fstat(report.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > self.max_report_bytes:
                        return failed
                    encoded = report.read(self.max_report_bytes + 1)
                    if len(encoded) > self.max_report_bytes:
                        return failed
                    payload = json.loads(encoded)
            if not validator(payload):
                return failed
            if self.report_from_stdout and self.retain_report:
                with path.open("xb") as report:
                    report.write(encoded)
        except (OSError, ValueError, TypeError, UnicodeError):
            return failed
        return ScannerResult(
            scanner_name=self.name,
            success=True,
            raw_output=payload,
            artifact_paths=[path] if self.retain_report else [],
            duration_ms=completed.duration_ms,
        )

    def get_version(self) -> str:
        import subprocess

        try:
            result = subprocess.run(
                [self.binary_name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception:
            return ""
