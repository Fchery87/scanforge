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
    report_filename = "gitleaks-results.json"
    retain_report = False
    accepted_exit_codes = frozenset({0, 1})

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "detect",
            "--source",
            "/workspace/source",
            "--report-format",
            "json",
            "--report-path",
            "/workspace/output/gitleaks-results.json",
            "--no-git",
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        return self._parse_report(
            completed,
            output_directory,
            lambda report: (
                isinstance(report, list)
                and all(
                    isinstance(item, dict) and isinstance(item.get("RuleID"), str) and isinstance(item.get("File"), str)
                    for item in report
                )
            ),
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
