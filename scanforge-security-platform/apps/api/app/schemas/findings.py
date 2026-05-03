from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FindingCategory(str):
    VULNERABILITY = "vulnerability"
    SECRET = "secret"
    DEPENDENCY_OUTDATED = "dependency_outdated"
    MALICIOUS_PATTERN = "malicious_pattern"
    CODE_QUALITY = "code_quality"
    CONTAINER_RISK = "container_risk"
    IAC_MISCONFIGURATION = "iac_misconfiguration"
    LICENSE_COMPLIANCE = "license_compliance"


class FindingSeverity(str):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str):
    OPEN = "open"
    REVIEWING = "reviewing"
    TO_FIX = "to_fix"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"
    DUPLICATE = "duplicate"
    NOT_OBSERVED = "not_observed"
    FIXED = "fixed"


class FindingInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_id: UUID
    scan_id: UUID
    scanner_run_id: UUID | None
    path: str | None
    line_start: int | None
    line_end: int | None
    package_name: str | None
    installed_version: str | None
    fixed_version: str | None
    evidence_json: dict | None
    created_at: datetime


class FindingReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_id: UUID
    reference_type: str
    reference_value: str
    url: str | None
    created_at: datetime


class FindingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_id: UUID
    event_type: str
    actor_user_id: UUID | None
    reason: str | None
    metadata_json: dict | None
    created_at: datetime


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    repository_id: UUID
    category: str
    severity: str
    status: str
    title: str
    description: str | None
    canonical_fingerprint: str
    primary_scanner: str | None
    confidence_score: float | None
    risk_score: int | None = None
    fixed_version: str | None
    metadata_json: dict | None
    assignee_user_id: UUID | None = None
    assignee_name: str | None = None
    assignee_email: str | None = None
    due_date: date | None = None
    sla_status: dict | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class FindingDetailResponse(FindingResponse):
    instances: list[FindingInstanceResponse] = []
    references: list[FindingReferenceResponse] = []
    events: list[FindingEventResponse] = []
    remediation_guidance: dict | None = None


class FindingSuppress(BaseModel):
    reason: str = Field(..., min_length=1)
    rule_id: UUID | None = None


class FindingResolve(BaseModel):
    fixed_version: str | None = None
    reason: str | None = None


class FindingBulkAction(BaseModel):
    finding_ids: list[UUID]
    action: str = Field(..., pattern="^(suppress|resolve|accept_risk|mark_duplicate)$")
    reason: str = Field(..., min_length=1)


class FindingTriageUpdate(BaseModel):
    assignee_user_id: UUID | None = None
    due_date: date | None = None


class FindingStats(BaseModel):
    total: int
    open: int
    fixed: int
    suppressed: int
    by_severity: dict[str, int]
    by_category: dict[str, int]


class NormalizedFindingInput(BaseModel):
    category: str
    severity: str
    title: str
    description: str | None = None
    canonical_fingerprint: str
    primary_scanner: str | None = None
    confidence_score: float | None = None
    fixed_version: str | None = None
    metadata_json: dict | None = None
    instance: dict | None = None
    references: list[dict] | None = None
