# ruff: noqa: TC001, TC003
from __future__ import annotations

import json
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.canonical_findings import CanonicalFindingCandidate

MAX_METADATA_BYTES = 64 * 1024
MAX_COMPLETION_BYTES = 8 * 1024 * 1024


class ScannerRunCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanner_name: str = Field(min_length=1, max_length=50)
    scanner_version: str | None = Field(default=None, max_length=64)
    status: str
    duration_ms: int | None = Field(default=None, ge=0)
    exit_code: int | None = None
    error_message: str | None = Field(default=None, max_length=4096)
    artifact_uri: str | None = Field(default=None, max_length=1024)
    metadata_json: dict[str, Any] | None = None

    @field_validator("metadata_json")
    @classmethod
    def bounded_metadata(cls, value):
        if value is not None and "scanner_version" in value:
            raise ValueError("scanner_version belongs to the scanner result, not metadata")
        if value is not None and len(json.dumps(value).encode()) > MAX_METADATA_BYTES:
            raise ValueError("scanner metadata exceeds 64 KiB")
        return value


class ScanCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[1] = 1
    winning_attempt_id: UUID
    observed_commit_sha: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
    execution_revision: int = Field(ge=0)
    findings: list[CanonicalFindingCandidate] = Field(default_factory=list, max_length=10000)
    scanner_runs: list[ScannerRunCompletion] = Field(default_factory=list, max_length=7)
    summary_json: dict[str, Any] = Field(default_factory=dict)
    artifact_uris: dict[str, Any] = Field(default_factory=dict)

    @field_validator("summary_json", "artifact_uris")
    @classmethod
    def bounded_metadata(cls, value):
        if len(json.dumps(value).encode()) > MAX_METADATA_BYTES:
            raise ValueError("completion metadata exceeds 64 KiB")
        return value

    @model_validator(mode="after")
    def bounded_payload(self) -> Self:
        if len(self.model_dump_json().encode()) > MAX_COMPLETION_BYTES:
            raise ValueError("completion evidence exceeds 8 MiB")
        return self


class ScanCompletionResponse(BaseModel):
    scan_id: UUID
    status: str
    inserted_findings: int
    updated_findings: int
    scanner_runs: int
    scanner_runs_complete: bool = False
    winning_attempt_id: UUID | None = None
    execution_revision: int | None = None
    evidence_digest: str | None = None
    replayed: bool = False
