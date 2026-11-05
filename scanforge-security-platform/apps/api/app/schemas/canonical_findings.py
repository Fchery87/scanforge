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
    model_config = ConfigDict(extra="forbid")

    type: str = "unknown"
    value: str = ""
    url: str | None = None


# Default policy for scanners not listed below. Policy versions are per scanner
# so one scanner can move to a new identity policy without making the others'
# findings non-comparable (ADR-014).
CURRENT_FINGERPRINT_VERSION = "fp.v2"

SCANNER_FINGERPRINT_VERSIONS: dict[str, str] = {
    "semgrep": "fp.v3",
    "checkov": "fp.v3",
    "gitleaks": "fp.v3",
}


def fingerprint_version_for_scanner(scanner_name: str | None) -> str:
    """Fingerprint policy a scanner's findings are produced under today."""
    return SCANNER_FINGERPRINT_VERSIONS.get(scanner_name or "", CURRENT_FINGERPRINT_VERSION)


class CanonicalFindingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_fingerprint: str = Field(min_length=1, max_length=255)
    fingerprint_version: str = Field(default=CURRENT_FINGERPRINT_VERSION, min_length=1, max_length=32)
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

