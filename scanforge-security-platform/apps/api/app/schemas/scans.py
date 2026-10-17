from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScanTriggerType(str):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    PULL_REQUEST = "pull_request"


class ScanStatus(str):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ScanType(str):
    FULL = "full"
    DIFF = "diff"
    DEPENDENCIES = "dependencies"
    SECRETS = "secrets"


class ScanCreate(BaseModel):
    repository_id: UUID
    trigger_type: str = Field(default="manual", pattern="^(manual|scheduled|webhook|pull_request)$")
    branch_name: str | None = Field(None, max_length=255)
    commit_sha: str | None = Field(None, max_length=64)
    base_sha: str | None = Field(None, max_length=64)
    pull_request_number: int | None = None
    scan_type: str = Field(default="full", pattern="^(full|diff|dependencies|secrets)$")


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    trigger_type: str
    scan_type: str
    status: str
    contract_version: str = "2026-10-beta.v1"
    branch_name: str | None
    full_ref_name: str | None = None
    branch_generation_number: int = 1
    ancestry_status: str = "unknown"
    commit_sha: str | None
    base_sha: str | None = None
    pull_request_number: int | None
    requested_by_user_id: UUID | None
    error_message: str | None
    summary_json: dict | None
    coverage_completeness: str = "unknown"
    closure_eligible: bool = False
    cleanup_state: str = "not_required"
    superseded_by_scan_id: UUID | None = None
    supersession_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ScannerRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    scanner_name: str
    scanner_version: str | None
    status: str
    outcome_status: str = "completed"
    parser_version: str | None = None
    rules_digest: str | None = None
    db_digest: str | None = None
    db_published_at: datetime | None = None
    db_freshness_state: str = "unverified"
    image_digest: str | None = None
    artifact_availability: str = "unavailable"
    closure_eligible: bool = False
    duration_ms: int | None
    exit_code: int | None
    error_message: str | None
    artifact_uri: str | None
    artifact_download_url: str | None = None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime


class ScanDetailResponse(ScanResponse):
    scanner_runs: list[ScannerRunResponse] = []


class ScanCancel(BaseModel):
    reason: str | None = None


class ScanStatusUpdate(BaseModel):
    status: str | None = None
    error_message: str | None = None
    summary_json: dict | None = None

