from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ScanContext:
    scan_id: str
    organization_id: str
    repository_id: str
    project_id: str
    branch: str | None
    commit_sha: str | None
    job_id: str
    user_id: str | None = None
    repo_path: Path | None = None
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))
    scanner_results: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    artifact_uris: dict = field(default_factory=dict)
    scanner_run_ids: dict = field(default_factory=dict)
    changed_files: list[str] | None = None
    expected_scanners: list[str] | None = None
    coverage_scope: dict | None = None
    critical_count: int = 0
    high_count: int = 0
    scan_failed: bool = False
    error_message: str | None = None
    ai_annotated_count: int = 0
    ai_skipped_count: int = 0
