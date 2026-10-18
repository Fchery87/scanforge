from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult, write_sanitized_output
from app.security.proc_env import build_contained_env
from app.security.secret_evidence import sanitize_trivy_output


class TrivyAdapter(ScannerAdapter):
    name = "trivy"
    binary_name = "trivy"
    binary_env_var = "TRIVY_BINARY"
    db_backed = True

    def get_version(self) -> str:
        entry = self._read_manifest_entry()
        if isinstance(entry, dict) and entry.get("scanner_version"):
            return str(entry["scanner_version"])
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
        try:
            result = subprocess.run(
                [self.binary_name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=build_contained_env(),
            )
            match = re.search(r"Version:\s*([^\s]+)", result.stdout)
            if match:
                return match.group(1)
            return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        except Exception:
            return ""

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "fs",
            "--no-progress",
            "--skip-version-check",
            "--skip-db-update",
            "--offline-scan",
            "--format",
            "json",
            "--output",
            "/workspace/output/trivy-results.json",
            "--scanners",
            "vuln,secret,misconfig",
            "/workspace/source",
        )

    def _parse_output_file(
        self,
        output_file: Path,
        *,
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
        if not output_file.exists() or output_file.stat().st_size == 0:
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    error=stderr.strip() or "Trivy produced no JSON report",
                    outcome_status="invalid_output" if exit_code in (0, 1) else "failed",
                    exit_code=exit_code,
                )
            )
        try:
            parsed = json.loads(output_file.read_text())
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
                    error="Invalid or truncated Trivy JSON output",
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
                    error="Unexpected Trivy JSON root type",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        sanitized = sanitize_trivy_output(parsed)
        write_sanitized_output(output_file, json.dumps(sanitized, separators=(",", ":")))
        ok = exit_code in (0, 1) or bool(sanitized)
        return self._apply_provenance(
            ScannerResult(
                scanner_name=self.name,
                success=ok,
                raw_output=sanitized,
                artifact_paths=[output_file] if ok else [],
                version=self.get_version(),
                duration_ms=duration_ms,
                error="" if ok else (stderr.strip() or f"Trivy exited with code {exit_code}"),
                outcome_status="completed" if ok else "failed",
                exit_code=exit_code,
            )
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "trivy-results.json"
        return self._parse_output_file(
            output_file,
            exit_code=completed.exit_code,
            timed_out=completed.timed_out,
            duration_ms=completed.duration_ms,
            stderr=completed.stderr,
        )

    def run(self, repo_path: Path) -> ScannerResult:
        start = time.time()
        output_file = repo_path / "trivy-results.json"
        try:
            result = subprocess.run(
                [
                    self.binary_name,
                    "fs",
                    "--no-progress",
                    "--skip-version-check",
                    "--skip-db-update",
                    "--offline-scan",
                    "--format",
                    "json",
                    "--output",
                    "trivy-results.json",
                    "--scanners",
                    "vuln,secret,misconfig",
                    str(repo_path),
                ],
                capture_output=True,
                text=True,
                timeout=self.runtime_timeout_seconds(),
                cwd=str(repo_path),
                env=build_contained_env(),
            )
            duration_ms = int((time.time() - start) * 1000)
            return self._parse_output_file(
                output_file,
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
