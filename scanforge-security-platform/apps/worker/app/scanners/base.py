import os
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
