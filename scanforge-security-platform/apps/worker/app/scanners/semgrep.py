from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult, write_sanitized_output
from app.security.proc_env import build_contained_env
from app.security.secret_evidence import sanitize_scanner_output

BUNDLED_SEMGREP_RULES_PATH = Path(__file__).resolve().parent / "rules" / "semgrep-rules.yml"
CONTAINER_SEMGREP_RULES_PATH = Path("/opt/scanner-rules/semgrep-rules.yml")


class SemgrepAdapter(ScannerAdapter):
    name = "semgrep"
    binary_name = "semgrep"
    binary_env_var = "SEMGREP_BINARY"
    db_backed = False

    def local_rules_path(self) -> Path:
        override = os.environ.get("SEMGREP_RULES_PATH")
        if override:
            return Path(override)
        if CONTAINER_SEMGREP_RULES_PATH.exists():
            return CONTAINER_SEMGREP_RULES_PATH
        return BUNDLED_SEMGREP_RULES_PATH

    def default_rules_digest(self) -> str | None:
        rules_file = self.local_rules_path()
        if rules_file.exists():
            return "sha256:" + hashlib.sha256(rules_file.read_bytes()).hexdigest()
        return super().default_rules_digest()

    def get_version(self) -> str:
        entry = self._read_manifest_entry()
        if isinstance(entry, dict) and entry.get("scanner_version"):
            return str(entry["scanner_version"])
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
        raw = super().get_version()
        return raw.splitlines()[0].strip() if raw else ""

    def runtime_arguments(self) -> tuple[str, ...]:
        rules_target = os.environ.get(
            "SEMGREP_CONTAINER_RULES_PATH",
            str(CONTAINER_SEMGREP_RULES_PATH)
            if CONTAINER_SEMGREP_RULES_PATH.exists()
            else str(self.local_rules_path()),
        )
        return (
            "scan",
            "--json",
            "--disable-version-check",
            "--metrics=off",
            "--jobs",
            "1",
            "--config",
            rules_target,
            "--json-output",
            "/workspace/output/semgrep-results.json",
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
        repo_root: Path | None = None,
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
                    error=stderr.strip() or "Semgrep produced no JSON report",
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
                    error="Invalid or truncated Semgrep JSON output",
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
                    error="Unexpected Semgrep JSON root type",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        if isinstance(parsed, dict) and repo_root is not None:
            prefix = str(repo_root.resolve()) + "/"
            raw_prefix = str(repo_root) + "/"
            for item in parsed.get("results", []) or []:
                if isinstance(item, dict):
                    p_str = str(item.get("path") or "")
                    if p_str.startswith(prefix):
                        item["path"] = p_str[len(prefix) :]
                    elif p_str.startswith(raw_prefix):
                        item["path"] = p_str[len(raw_prefix) :]
        sanitized = sanitize_scanner_output(self.name, parsed)
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
                error="" if ok else (stderr.strip() or f"Semgrep exited with code {exit_code}"),
                outcome_status="completed" if ok else "failed",
                exit_code=exit_code,
            )
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "semgrep-results.json"
        return self._parse_output_file(
            output_file,
            exit_code=completed.exit_code,
            timed_out=completed.timed_out,
            duration_ms=completed.duration_ms,
            stderr=completed.stderr,
        )

    def run(self, repo_path: Path) -> ScannerResult:
        start = time.time()
        output_file = repo_path / "semgrep-results.json"
        try:
            config_arg = str(self.local_rules_path()) if self.local_rules_path().exists() else "auto"
            result = subprocess.run(
                [
                    self.binary_name,
                    "scan",
                    "--json",
                    "--disable-version-check",
                    "--metrics=off",
                    "--jobs",
                    "1",
                    "--config",
                    config_arg,
                    "--json-output",
                    "semgrep-results.json",
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
                repo_root=repo_path,
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
