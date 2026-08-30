# ruff: noqa: TC001, TC003
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.canonical_findings import CanonicalFindingCandidate


class ScannerRunCompletion(BaseModel):
    scanner_name: str = Field(min_length=1, max_length=50)
    scanner_version: str | None = None
    status: str
    duration_ms: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    artifact_uri: str | None = None
    metadata_json: dict[str, Any] | None = None


class ScanCompletionRequest(BaseModel):
    findings: list[CanonicalFindingCandidate] = Field(default_factory=list)
    scanner_runs: list[ScannerRunCompletion] = Field(default_factory=list)
    summary_json: dict[str, Any] = Field(default_factory=dict)
    artifact_uris: dict[str, Any] = Field(default_factory=dict)


class ScanCompletionResponse(BaseModel):
    scan_id: UUID
    status: str
    inserted_findings: int
    updated_findings: int
    scanner_runs: int
    replayed: bool = False
