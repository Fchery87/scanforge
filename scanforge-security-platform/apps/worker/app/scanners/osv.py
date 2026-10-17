from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

from app.scanners.base import ScannerAdapter, ScannerResult
from app.security.proc_env import build_contained_env
from app.security.secret_evidence import sanitize_scanner_output


class OsvAdapter(ScannerAdapter):
    name = "osv"
    binary_name = "osv-scanner"
    binary_env_var = "OSV_SCANNER_BINARY"
    db_backed = True

    def get_version(self) -> str:
        entry = self._read_manifest_entry()
        if isinstance(entry, dict) and entry.get("scanner_version"):
            return str(entry["scanner_version"])
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
        raw = super().get_version()
        match = re.search(r"osv-scanner version:\s*([^\s]+)", raw)
        if match:
            return match.group(1)
        return raw.splitlines()[0] if raw else ""

    def runtime_arguments(self) -> tuple[str, ...]:
        return (
            "scan",
            "--experimental-offline-vulnerabilities",
            "--no-ignore",
            "--format",
            "json",
            "--output",
            "/workspace/output/osv-results.json",
            "-r",
            "/workspace/source",
        )

    def _parse_output_file(
        self,
        output_file: Path,
        *,
        exit_code: int,
        timed_out: bool,
        duration_ms: int,
        stdout: str,
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
        combined_msg = f"{stdout}\n{stderr}"
        if exit_code == 128 and "No package sources found" in combined_msg:
            empty_payload = {"results": []}
            output_file.write_text(json.dumps(empty_payload, separators=(",", ":")))
            return self._apply_provenance(
                ScannerResult(
                    scanner_name=self.name,
                    success=True,
                    raw_output=empty_payload,
                    artifact_paths=[output_file],
                    version=self.get_version(),
                    duration_ms=duration_ms,
                    outcome_status="completed",
                    exit_code=0,
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
                    error=stderr.strip() or "OSV-Scanner produced no JSON report",
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
                    error="Invalid or truncated OSV-Scanner JSON output",
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
                    error="Unexpected OSV-Scanner JSON root type",
                    outcome_status="invalid_output",
                    exit_code=exit_code,
                )
            )
        if isinstance(parsed, dict) and repo_root is not None:
            prefix = str(repo_root.resolve()) + "/"
            raw_prefix = str(repo_root) + "/"
            for res_item in parsed.get("results", []) or []:
                if isinstance(res_item, dict) and isinstance(res_item.get("source"), dict):
                    src_path = str(res_item["source"].get("path") or "")
                    if src_path.startswith(prefix):
                        res_item["source"]["path"] = src_path[len(prefix) :]
                    elif src_path.startswith(raw_prefix):
                        res_item["source"]["path"] = src_path[len(raw_prefix) :]
        sanitized = sanitize_scanner_output(self.name, parsed)
        output_file.write_text(json.dumps(sanitized, separators=(",", ":")))
        ok = exit_code in (0, 1) or bool(sanitized)
        return self._apply_provenance(
            ScannerResult(
                scanner_name=self.name,
                success=ok,
                raw_output=sanitized,
                artifact_paths=[output_file] if ok else [],
                version=self.get_version(),
                duration_ms=duration_ms,
                error="" if ok else (stderr.strip() or f"OSV-Scanner exited with code {exit_code}"),
                outcome_status="completed" if ok else "failed",
                exit_code=exit_code,
            )
        )

    def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
        output_file = output_directory / "osv-results.json"
        return self._parse_output_file(
            output_file,
            exit_code=completed.exit_code,
            timed_out=completed.timed_out,
            duration_ms=completed.duration_ms,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def run(self, repo_path: Path) -> ScannerResult:
        start = time.time()
        output_file = repo_path / "osv-results.json"
        try:
            extra_flags: list[str] = []
            local_db_dir = os.environ.get("OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY")
            if local_db_dir:
                extra_flags.extend(["--experimental-offline-vulnerabilities", "--no-ignore"])
            cmd = [
                self.binary_name,
                *extra_flags,
                "--format",
                "json",
                "--output",
                "osv-results.json",
                "-r",
                str(repo_path),
            ]
            env = build_contained_env(
                {"OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": local_db_dir} if local_db_dir else None
            )
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.runtime_timeout_seconds(),
                cwd=str(repo_path),
                env=env,
            )
            duration_ms = int((time.time() - start) * 1000)
            return self._parse_output_file(
                output_file,
                exit_code=result.returncode,
                timed_out=False,
                duration_ms=duration_ms,
                stdout=result.stdout,
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
