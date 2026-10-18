from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult, write_sanitized_output
from app.security.proc_env import build_contained_env
from app.security.secret_evidence import sanitize_scanner_output


class CheckovAdapter(ScannerAdapter):
    name = "checkov"
    binary_name = "checkov"
    binary_env_var = "CHECKOV_BINARY"
    db_backed = False

    def _extra_filter_args(self) -> list[str]:
        extra: list[str] = []
        frameworks = os.environ.get("CHECKOV_FRAMEWORKS", "").strip()
        if frameworks:
            extra.extend(["--framework", *[f.strip() for f in frameworks.split(",") if f.strip()]])
        checks = os.environ.get("CHECKOV_CHECKS", "").strip()
        if checks:
            extra.extend(["--check", checks])
        return extra

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "--directory",
            "/workspace/source",
            *self._extra_filter_args(),
            "--quiet",
            "--skip-download",
            "--output",
            "json",
        )

    def _parse_stdout_or_file(
        self,
        *,
        stdout: str,
        output_file: Path,
        exit_code: int,
        timed_out: bool,
        duration_ms: int,
        stderr: str,
    ) -> ScannerResult:
        if timed_out:
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    error="Scanner timed out",
                    outcome_status="timed_out",
                    exit_code=exit_code,
                )
            )
        raw_text = (stdout or "").strip()
        if not raw_text and output_file.exists() and output_file.stat().st_size > 0:
            raw_text = output_file.read_text().strip()
        if not raw_text:
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    error=stderr.strip() or "Checkov produced no JSON output",
                    outcome_status="invalid_output" if exit_code in (0, 1) else "failed",
                    exit_code=exit_code,
                )
            )
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    error="Invalid or truncated Checkov JSON output",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        if not isinstance(parsed, (dict, list)):
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    error="Unexpected Checkov JSON root type",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        sanitized = sanitize_scanner_output(self.name, parsed)
        write_sanitized_output(output_file, json.dumps(sanitized, indent=2))
        ok = exit_code in (0, 1) or bool(sanitized)
        return self._apply_provenance(
            ScannerResult(
                scanner_name=self.name,
                success=ok,
                raw_output=sanitized,
                artifact_paths=[output_file] if ok else [],
                version=self.get_version(),
                duration_ms=duration_ms,
                error="" if ok else (stderr.strip() or f"Checkov exited with code {exit_code}"),
                outcome_status="completed" if ok else "failed",
                exit_code=exit_code,
            )
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "checkov-results.json"
        return self._parse_stdout_or_file(
            stdout=completed.stdout,
            output_file=output_file,
            exit_code=completed.exit_code,
            timed_out=completed.timed_out,
            duration_ms=completed.duration_ms,
            stderr=completed.stderr,
        )

    def run(self, repo_path: Path) -> ScannerResult:
        start = time.time()
        output_file = repo_path / "checkov-results.json"
        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "--directory",
                    str(repo_path),
                    *self._extra_filter_args(),
                    "--quiet",
                    "--skip-download",
                    "--output",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=self.runtime_timeout_seconds(),
                cwd=str(repo_path),
                env=build_contained_env({"BC_SKIP_MAPPING": "TRUE"}),
            )
            duration_ms = int((time.time() - start) * 1000)
            return self._parse_stdout_or_file(
                stdout=result.stdout,
                output_file=output_file,
                exit_code=result.returncode,
                timed_out=False,
                duration_ms=duration_ms,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    error="Scanner timed out",
                    duration_ms=int((time.time() - start) * 1000),
                    outcome_status="timed_out",
                )
            )
        except Exception as e:
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    error=str(e),
                    outcome_status="failed",
                )
            )
