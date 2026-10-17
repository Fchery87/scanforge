from enum import StrEnum


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    SECURITY_REVIEWER = "security_reviewer"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class RepoProvider(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    MANUAL = "manual"


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ScanTriggerType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    PULL_REQUEST = "pull_request"


class CoverageCompleteness(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    LEGACY_UNVERIFIED = "legacy_unverified"


class ScannerOutcomeStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED_UNAPPLICABLE = "skipped_unapplicable"
    SKIPPED_DISABLED = "skipped_disabled"
    CANCELED = "canceled"


class DatabaseFreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class ArtifactVerificationState(StrEnum):
    STAGED = "staged"
    VERIFIED_IMMUTABLE = "verified_immutable"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    EXPIRED = "expired"
    ERASED = "erased"


class CleanupState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    COMPLETED = "completed"
    INCIDENT_HOST_UNREACHABLE = "incident_host_unreachable"
    FAILED = "failed"


class AncestryStatus(StrEnum):
    VERIFIED_INITIAL = "verified_initial"
    VERIFIED_DESCENDANT = "verified_descendant"
    RECREATED_OR_FORCE_PUSHED = "recreated_or_force_pushed"
    UNKNOWN = "unknown"
    RETIRED = "retired"


class DispatchObligationStatus(StrEnum):
    AWAITING_DISPATCH = "awaiting_dispatch"
    LEASED = "leased"
    DISPATCHED = "dispatched"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    CANCELED = "canceled"


class FindingDispositionStatus(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    TO_FIX = "to_fix"
    NOT_OBSERVED = "not_observed"
    FIXED = "fixed"
    RISK_ACCEPTED = "risk_accepted"
    FALSE_POSITIVE = "false_positive"
    DUPLICATE = "duplicate"
    RETIRED_SCOPE = "retired_scope"
    LEGACY_UNVERIFIED = "legacy_unverified"

