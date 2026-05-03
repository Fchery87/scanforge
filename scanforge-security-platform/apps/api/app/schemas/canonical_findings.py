from pydantic import BaseModel, ConfigDict


class CanonicalFindingInstance(BaseModel):
    model_config = ConfigDict(extra="allow")

    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    package_name: str | None = None
    installed_version: str | None = None
    fixed_version: str | None = None


class CanonicalFindingReference(BaseModel):
    type: str = "unknown"
    value: str = ""
    url: str | None = None


class CanonicalFindingCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    canonical_fingerprint: str
    severity: str = "medium"
    category: str = "unknown"
    title: str = "Untitled Finding"
    description: str | None = None
    primary_scanner: str | None = None
    confidence_score: float | None = None
    fixed_version: str | None = None
    metadata_json: dict | None = None
    instance: CanonicalFindingInstance | None = None
    references: list[CanonicalFindingReference] = []
