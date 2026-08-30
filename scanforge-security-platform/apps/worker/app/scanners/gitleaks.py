from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult


class GitleaksAdapter(ScannerAdapter):
    name = "gitleaks"
    binary_name = "gitleaks"
    binary_env_var = "GITLEAKS_BINARY"

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "detect",
            "--source",
            "/workspace/source",
            "--report-format",
            "json",
            "--report-path",
            "/workspace/output/gitleaks-report.json",
            "--no-git",
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "gitleaks-report.json"
        output = []
        if output_file.exists():
            try:
                output = json.loads(output_file.read_text())
            except json.JSONDecodeError:
                output = []
        return ScannerResult(
            scanner_name=self.name,
            success=completed.exit_code in (0, 1) and not completed.timed_out,
            raw_output=output,
            artifact_paths=[],
            version=self.get_version(),
            duration_ms=completed.duration_ms,
            error=completed.stderr if completed.exit_code not in (0, 1) else "",
        )

    def run(self, repo_path: Path) -> ScannerResult:
        start = time.time()
        report_path = repo_path / ".gitleaks-report.json"
        try:
            result = subprocess.run(  # noqa: S603
                [
                    self.binary_name,
                    "detect",
                    "--source",
                    str(repo_path),
                    "--report-format",
                    "json",
                    "--report-path",
                    str(report_path),
                    "--no-git",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            output: list | dict = []
            if report_path.exists() and report_path.stat().st_size:
                try:
                    output = json.loads(report_path.read_text())
                except json.JSONDecodeError:
                    output = []
            return ScannerResult(
                scanner_name=self.name,
                success=result.returncode in (0, 1),
                raw_output=output,
                artifact_paths=[],
                version=self.get_version(),
                duration_ms=int((time.time() - start) * 1000),
                error=result.stderr.strip() if result.returncode not in (0, 1) else "",
            )
        except subprocess.TimeoutExpired:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error="Scanner timed out",
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as exc:
            return ScannerResult(
                scanner_name=self.name,
                success=False,
                raw_output={},
                artifact_paths=[],
                error=str(exc),
            )
        finally:
            report_path.unlink(missing_ok=True)
