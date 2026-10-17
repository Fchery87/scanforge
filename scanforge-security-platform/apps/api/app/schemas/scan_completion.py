# ruff: noqa: TC001, TC003
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.canonical_findings import CanonicalFindingCandidate


class ScannerRunCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanner_name: str = Field(min_length=1, max_length=50)
    scanner_version: str | None = None
    status: str
    outcome_status: str | None = None
    parser_version: str | None = None
    rules_digest: str | None = None
    db_digest: str | None = None
    db_published_at: datetime | None = None
    db_freshness_state: str = "unverified"
    image_digest: str | None = None
    artifact_availability: str = "unavailable"
    duration_ms: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    artifact_uri: str | None = None
    metadata_json: dict[str, Any] | None = None


class ScanCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default="2026-10-beta.v1", min_length=1, max_length=32)
    winning_attempt_id: UUID
    execution_revision: int = Field(ge=0)
    worker_incarnation_id: str | None = Field(default=None, max_length=128)
    findings: list[CanonicalFindingCandidate] = Field(default_factory=list)
    scanner_runs: list[ScannerRunCompletion] = Field(default_factory=list)
    summary_json: dict[str, Any] = Field(default_factory=dict)
    artifact_uris: dict[str, Any] = Field(default_factory=dict)


class ScanCompletionResponse(BaseModel):
    scan_id: UUID
    status: str
    contract_version: str = "2026-10-beta.v1"
    inserted_findings: int
    updated_findings: int
    scanner_runs: int
    scanner_runs_complete: bool = False
    coverage_completeness: str = "unknown"
    closure_eligible: bool = False
    artifact_availability: str = "unavailable"
    winning_attempt_id: UUID | None = None
    execution_revision: int | None = None
    evidence_digest: str | None = None
    replayed: bool = False

