from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from app.security.proc_env import build_contained_env

DEFAULT_SCANNER_MANIFEST_PATH = Path("/opt/scanner-manifest.json")
MAX_SCANNER_DB_AGE = timedelta(days=7)
CURRENT_SCANNER_PARSER_VERSION = "2026-10-parser.v1"


@dataclass
class ScannerResult:
    scanner_name: str
    success: bool
    raw_output: dict[str, Any] | list[Any]
    artifact_paths: list[Path] = field(default_factory=list)
    version: str = ""
    duration_ms: int = 0
    error: str = ""
    outcome_status: str = ""
    exit_code: int | None = None
    parser_version: str = CURRENT_SCANNER_PARSER_VERSION
    rules_digest: str | None = None
    db_digest: str | None = None
    db_published_at: str | None = None
    db_freshness_state: str = "not_applicable"
    image_digest: str | None = None
    output_directory: Path | None = None

    def __post_init__(self) -> None:
        if not self.outcome_status:
            self.outcome_status = "completed" if self.success else "failed"


class ScannerAdapter(ABC):
    name: str = "base"
    binary_name: str = ""
    binary_env_var: str | None = None
    db_backed: bool = False
    parser_version: str = CURRENT_SCANNER_PARSER_VERSION

    def __init__(self) -> None:
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
        from app.runtime.models import ScanRuntimeRequest

        arguments = self.runtime_arguments()
        if not arguments or "--version" in arguments or arguments == ("version",):
            raise NotImplementedError(
                f"{self.name} does not implement contained analysis execution"
            )

        output_directory = Path(mkdtemp(prefix=f"scan_{self.name}_output_"))
        try:
            os.chmod(output_directory, 0o1777)  # noqa: S103  # scanner UID needs writes; sticky bit limits deletion
        except OSError:
            pass
        keep_output_dir = False
        try:
            request = ScanRuntimeRequest(
                executable=self.binary_name,
                arguments=arguments,
                source_directory=repo_path,
                output_directory=output_directory,
                timeout_seconds=self.runtime_timeout_seconds(),
            )
            completed = runtime.run(request)
            result = self.parse_runtime_result(completed, output_directory)
            self._apply_provenance(result)
            if completed.image_digest:
                result.image_digest = completed.image_digest
            if self.name != "gitleaks" and result.artifact_paths:
                result.output_directory = output_directory
                keep_output_dir = True
            return result
        finally:
            if not keep_output_dir:
                shutil.rmtree(output_directory, ignore_errors=True)

    def runtime_arguments(self) -> tuple[str, ...]:
        raise NotImplementedError(
            f"{self.name} does not implement contained runtime_arguments"
        )

    def runtime_timeout_seconds(self) -> int:
        return 600

    def parse_runtime_result(self, completed, _output_directory: Path) -> ScannerResult:
        raise NotImplementedError(
            f"{self.name} does not implement contained parse_runtime_result"
        )

    def get_version(self) -> str:
        manifest_entry = self._read_manifest_entry()
        if isinstance(manifest_entry, dict) and manifest_entry.get("scanner_version"):
            return str(manifest_entry["scanner_version"])
        if isinstance(manifest_entry, str) and manifest_entry.strip():
            return manifest_entry.strip()
        try:
            result = subprocess.run(
                [self.binary_name, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                env=build_contained_env(),
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _manifest_path(self) -> Path:
        override = os.environ.get("SCANNER_MANIFEST_PATH")
        if override:
            return Path(override)
        return DEFAULT_SCANNER_MANIFEST_PATH

    def _read_manifest_root(self) -> dict[str, Any]:
        manifest_path = self._manifest_path()
        if not manifest_path.exists():
            return {}
        try:
            loaded = json.loads(manifest_path.read_text())
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def _read_manifest_entry(self) -> dict[str, Any] | str | None:
        root = self._read_manifest_root()
        scanners = root.get("scanners")
        if isinstance(scanners, dict):
            if self.name in scanners:
                return scanners[self.name]
            if self.binary_name in scanners:
                return scanners[self.binary_name]
        if self.name in root:
            return root[self.name]
        if self.binary_name in root:
            return root[self.binary_name]
        return None

    def resolve_provenance(self, *, now: datetime | None = None) -> dict[str, Any]:
        eval_now = now or datetime.now(UTC)
        root = self._read_manifest_root()
        entry = self._read_manifest_entry()
        entry_dict = entry if isinstance(entry, dict) else {}

        scanner_version = (
            str(entry_dict.get("scanner_version") or (entry if isinstance(entry, str) else "")).strip()
            or self.get_version()
        )
        parser_version = str(entry_dict.get("parser_version") or self.parser_version)
        rules_digest = entry_dict.get("rules_digest") or self.default_rules_digest()
        db_digest = entry_dict.get("db_digest")
        db_published_at = (
            entry_dict.get("db_published_at")
            or os.environ.get(f"{self.name.upper()}_DB_PUBLISHED_AT")
            or os.environ.get("SCANNER_DB_PUBLISHED_AT")
        )
        image_digest = (
            entry_dict.get("image_digest")
            or root.get("image_digest")
            or os.environ.get("SCANNER_IMAGE_DIGEST")
        )

        if not self.db_backed:
            db_freshness_state = "not_applicable"
        elif not db_published_at:
            db_freshness_state = "unverifiable"
        else:
            parsed_dt = _parse_iso_datetime(str(db_published_at))
            if parsed_dt is None:
                db_freshness_state = "unverifiable"
            elif eval_now - parsed_dt <= MAX_SCANNER_DB_AGE:
                db_freshness_state = "fresh"
            else:
                db_freshness_state = "stale"

        return {
            "version": scanner_version,
            "parser_version": parser_version,
            "rules_digest": rules_digest,
            "db_digest": db_digest,
            "db_published_at": db_published_at,
            "db_freshness_state": db_freshness_state,
            "image_digest": image_digest,
        }

    def default_rules_digest(self) -> str | None:
        return hashlib.sha256(f"{self.name}:{self.parser_version}".encode()).hexdigest()

    def _apply_provenance(self, result: ScannerResult, *, now: datetime | None = None) -> ScannerResult:
        prov = self.resolve_provenance(now=now)
        if not result.version:
            result.version = prov["version"]
        result.parser_version = prov["parser_version"]
        result.rules_digest = prov["rules_digest"]
        result.db_digest = prov["db_digest"]
        result.db_published_at = prov["db_published_at"]
        result.db_freshness_state = prov["db_freshness_state"]
        result.image_digest = prov["image_digest"]
        return result


def _parse_iso_datetime(value: str) -> datetime | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(cleaned)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    except ValueError:
        return None
