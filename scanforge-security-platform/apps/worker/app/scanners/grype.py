from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult, write_sanitized_output
from app.security.proc_env import build_contained_env
from app.security.secret_evidence import sanitize_scanner_output

BUNDLED_GRYPE_CONFIG_PATH = Path(__file__).resolve().parent / "rules" / "grype-config.yaml"
CONTAINER_GRYPE_CONFIG_PATH = Path("/opt/scanner-rules/grype-config.yaml")


class GrypeAdapter(ScannerAdapter):
    name = "grype"
    binary_name = "grype"
    binary_env_var = "GRYPE_BINARY"
    db_backed = True

    def local_config_path(self) -> Path:
        override = os.environ.get("GRYPE_CONFIG_PATH")
        if override:
            return Path(override)
        if CONTAINER_GRYPE_CONFIG_PATH.exists():
            return CONTAINER_GRYPE_CONFIG_PATH
        return BUNDLED_GRYPE_CONFIG_PATH

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
            match = re.search(r"Version:\s*([^\s]+)", result.stdout)
            if match:
                return match.group(1)
            return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        except Exception:
            return ""

    def runtime_arguments(self) -> tuple[str, ...]:
        config_target = os.environ.get(
            "GRYPE_CONTAINER_CONFIG_PATH",
            str(CONTAINER_GRYPE_CONFIG_PATH)
            if CONTAINER_GRYPE_CONFIG_PATH.exists()
            else str(self.local_config_path()),
        )
        return (
            "--quiet",
            "-c",
            config_target,
            "dir:/workspace/source",
            "-o",
            "json",
            "--file",
            "/workspace/output/grype-results.json",
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
                    error=stderr.strip() or "Grype produced no JSON report",
                    outcome_status="invalid_output" if exit_code in (0, 1, 2) else "failed",
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
                    error="Invalid or truncated Grype JSON output",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        if not isinstance(parsed, (dict, list)) or (
            isinstance(parsed, dict) and "matches" not in parsed
        ):
            output_file.unlink(missing_ok=True)
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=False,
                    raw_output={},
                    artifact_paths=[],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    error="Grype output missing expected 'matches' schema",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        sanitized = sanitize_scanner_output(self.name, parsed)
        write_sanitized_output(output_file, json.dumps(sanitized, separators=(",", ":")))
        ok = exit_code in (0, 1, 2) or bool(sanitized)
        return self._apply_provenance(
            ScannerResult(
                scanner_name=self.name,
                success=ok,
                raw_output=sanitized,
                artifact_paths=[output_file] if ok else [],
                version=self.get_version(),
                duration_ms=duration_ms,
                error="" if ok else (stderr.strip() or f"Grype exited with code {exit_code}"),
                outcome_status="completed" if ok else "failed",
                exit_code=exit_code,
            )
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "grype-results.json"
        return self._parse_output_file(
            output_file,
            exit_code=completed.exit_code,
            timed_out=completed.timed_out,
            duration_ms=completed.duration_ms,
            stderr=completed.stderr,
        )

    def run(self, repo_path: Path) -> ScannerResult:
        start = time.time()
        output_file = repo_path / "grype-results.json"
        try:
            config_flags: list[str] = []
            if self.local_config_path().exists():
                config_flags = ["-c", str(self.local_config_path())]
            result = subprocess.run(
                [
                    self.binary_name,
                    "--quiet",
                    *config_flags,
                    f"dir:{repo_path}",
                    "-o",
                    "json",
                    "--file",
                    str(output_file),
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
