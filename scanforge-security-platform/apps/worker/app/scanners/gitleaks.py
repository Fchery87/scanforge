from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult
from app.security.proc_env import build_contained_env


def _relativize_gitleaks_records(records: list, repo_root: Path | None) -> list:
    prefix = str(repo_root.resolve()) + "/" if repo_root else ""
    cleaned = []
    for item in records:
        if not isinstance(item, dict):
            continue
        rec = dict(item)
        file_val = str(rec.get("File") or "")
        if prefix and file_val.startswith(prefix):
            file_val = file_val[len(prefix) :]
        elif repo_root and file_val.startswith(str(repo_root) + "/"):
            file_val = file_val[len(str(repo_root)) + 1 :]
        file_val = re.sub(r"^/workspace/source/?", "", file_val)
        rec["File"] = file_val
        cleaned.append(rec)
    return cleaned


class GitleaksAdapter(ScannerAdapter):
    name = "gitleaks"
    binary_name = "gitleaks"
    binary_env_var = "GITLEAKS_BINARY"
    db_backed = False

    def get_version(self) -> str:
        entry = self._read_manifest_entry()
        if isinstance(entry, dict) and entry.get("scanner_version"):
            return str(entry["scanner_version"])
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
        try:
            result = subprocess.run(
                [self.binary_name, "version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=build_contained_env(),
            )
            out = (result.stdout or "").strip()
            if out:
                return out.splitlines()[0].replace("gitleaks version ", "").strip()
        except Exception:
            pass
        return super().get_version()

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

    def _parse_report(
        self,
        report_path: Path,
        *,
        exit_code: int,
        timed_out: bool,
        duration_ms: int,
        stderr: str,
        repo_root: Path | None = None,
    ) -> ScannerResult:
        try:
            if timed_out:
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
            if exit_code not in (0, 1):
                return self._apply_provenance(
                    ScannerResult(
                        scanner_name=self.name,
                        success=False,
                        raw_output={},
                        artifact_paths=[],
                        version=self.get_version(),
                        duration_ms=duration_ms,
                        error=stderr.strip() or f"Gitleaks exited with code {exit_code}",
                        outcome_status="failed",
                        exit_code=exit_code,
                    )
                )
            if not report_path.exists() or report_path.stat().st_size == 0:
                if exit_code == 0:
                    return self._apply_provenance(
                        ScannerResult(
                            scanner_name=self.name,
                            success=True,
                            raw_output=[],
                            artifact_paths=[],
                            version=self.get_version(),
                            duration_ms=duration_ms,
                            outcome_status="completed",
                            exit_code=exit_code,
                        )
                    )
                return self._apply_provenance(
                    ScannerResult(
                        scanner_name=self.name,
                        success=False,
                        raw_output={},
                        artifact_paths=[],
                        version=self.get_version(),
                        duration_ms=duration_ms,
                        error="Gitleaks exited with findings code 1 but wrote no report",
                        outcome_status="invalid_output",
                        exit_code=exit_code,
                    )
                )
            try:
                parsed = json.loads(report_path.read_text())
            except json.JSONDecodeError:
                return self._apply_provenance(
                    ScannerResult(
                        scanner_name=self.name,
                        success=False,
                        raw_output={},
                        artifact_paths=[],
                        version=self.get_version(),
                        duration_ms=duration_ms,
                        error="Invalid or truncated Gitleaks JSON output",
                        outcome_status="invalid_output",
                        exit_code=exit_code,
                    )
                )
            if not isinstance(parsed, list):
                return self._apply_provenance(
                    ScannerResult(
                        scanner_name=self.name,
                        success=False,
                        raw_output={},
                        artifact_paths=[],
                        version=self.get_version(),
                        duration_ms=duration_ms,
                        error="Unexpected Gitleaks JSON root type",
                        outcome_status="invalid_output",
                        exit_code=exit_code,
                    )
                )
            output = _relativize_gitleaks_records(parsed, repo_root)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=True,
                    raw_output=output,
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    outcome_status="completed",
                    exit_code=exit_code,
                )
            )
        finally:
            report_path.unlink(missing_ok=True)

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "gitleaks-report.json"
        return self._parse_report(
            output_file,
            exit_code=completed.exit_code,
            timed_out=completed.timed_out,
            duration_ms=completed.duration_ms,
            stderr=completed.stderr,
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
                env=build_contained_env(),
            )
            return self._parse_report(
                report_path,
                exit_code=result.returncode,
                timed_out=False,
                duration_ms=int((time.time() - start) * 1000),
                stderr=result.stderr,
                repo_root=repo_path,
            )
        except subprocess.TimeoutExpired:
            report_path.unlink(missing_ok=True)
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
        except Exception as exc:
            report_path.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    error=str(exc),
                    outcome_status="failed",
                )
            )
        finally:
            report_path.unlink(missing_ok=True)
