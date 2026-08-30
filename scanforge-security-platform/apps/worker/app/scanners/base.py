import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ScannerResult:
    scanner_name: str
    success: bool
    raw_output: dict[str, Any]
    artifact_paths: list[Path] = field(default_factory=list)
    version: str = ""
    duration_ms: int = 0
    error: str = ""


class ScannerAdapter(ABC):
    name: str = "base"
    binary_name: str = ""
    binary_env_var: str | None = None

    def __init__(self):
        if self.binary_env_var:
            self.binary_name = os.environ.get(self.binary_env_var, self.binary_name)

    @abstractmethod
    def run(self, repo_path: Path) -> ScannerResult:
        raise NotImplementedError

    def run_contained(self, repo_path: Path, runtime) -> ScannerResult:
        """Execute this adapter inside the configured disposable runtime.

        Private-beta coordinators call this method. Existing ``run`` methods
        remain the local-development implementation and are never selected in
        private-beta mode.
        """
        from tempfile import mkdtemp

        from app.runtime.models import ScanRuntimeRequest

        output_directory = Path(mkdtemp(prefix=f"scan_{self.name}_output_"))
        try:
            request = ScanRuntimeRequest(
                executable=self.binary_name,
                arguments=self.runtime_arguments(),
                source_directory=repo_path,
                output_directory=output_directory,
                timeout_seconds=self.runtime_timeout_seconds(),
            )
            completed = runtime.run(request)
            return self.parse_runtime_result(completed, output_directory)
        finally:
            shutil.rmtree(output_directory, ignore_errors=True)

    def runtime_arguments(self) -> tuple[str, ...]:
        return ("--version",)

    def runtime_timeout_seconds(self) -> int:
        return 600

    def parse_runtime_result(self, completed, _output_directory: Path) -> ScannerResult:
        return ScannerResult(
            scanner_name=self.name,
            success=completed.exit_code == 0 and not completed.timed_out,
            raw_output={},
            artifact_paths=[],
            duration_ms=completed.duration_ms,
            error=completed.stderr,
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
