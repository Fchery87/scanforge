from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    pull_request_number: int | None = None
    base_commit_sha: str | None = Field(None, pattern="^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$")
    head_commit_sha: str | None = Field(None, pattern="^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$")
    scan_type: str = Field(default="full", pattern="^(full|diff|dependencies|secrets)$")

    @model_validator(mode="after")
    def validate_pull_request_context(self):
        if self.trigger_type == "pull_request":
            if not self.base_commit_sha or not self.head_commit_sha or not self.pull_request_number:
                raise ValueError("Pull request base, head, and number required")
            if self.commit_sha and self.commit_sha != self.head_commit_sha:
                raise ValueError("Pull request commit must match recorded head")
            self.commit_sha = self.head_commit_sha
        return self


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    trigger_type: str
    scan_type: str
    status: str
    branch_name: str | None
    commit_sha: str | None
    pull_request_number: int | None
    base_commit_sha: str | None = None
    head_commit_sha: str | None = None
    requested_by_user_id: UUID | None
    error_message: str | None
    summary_json: dict | None
    created_at: datetime
    updated_at: datetime


class ScannerRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    scanner_name: str
    scanner_version: str | None
    status: str
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
