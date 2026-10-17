from pydantic import BaseModel, ConfigDict, Field


class CanonicalFindingInstance(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    package_name: str | None = None
    installed_version: str | None = None
    fixed_version: str | None = None
    ai_annotation: dict | None = None


class CanonicalFindingReference(BaseModel):
    type: str = "unknown"
    value: str = ""
    url: str | None = None


class CanonicalFindingCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    canonical_fingerprint: str = Field(min_length=1, max_length=255)
    fingerprint_version: str = Field(default="fp.v2", min_length=1, max_length=32)
    severity: str = "medium"
    category: str = "unknown"
    title: str = "Untitled Finding"
    description: str | None = None
    primary_scanner: str | None = None
    confidence_score: float | None = None
    fixed_version: str | None = None
    advisory_id: str | None = None
    package_ecosystem: str | None = None
    package_name: str | None = None
    metadata_json: dict | None = None
    instance: CanonicalFindingInstance | None = None
    references: list[CanonicalFindingReference] = Field(default_factory=list)

