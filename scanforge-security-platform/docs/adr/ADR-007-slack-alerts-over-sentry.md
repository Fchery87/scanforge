# ADR-007: Slack webhook alerts over Sentry for error tracking

## Status
Accepted

## Decision
Use structured stdout JSON logs plus a Slack webhook (`SLACK_ALERT_WEBHOOK_URL`) for error visibility. Do not adopt Sentry or any other error-tracking SaaS.

## Rationale
ScanForge is a security-sensitive platform. Adding a third-party error aggregation SaaS (Sentry, Datadog, etc.) would:

1. Introduce a new subscription dependency
2. Risk transmitting stack traces, request payloads, or partial finding data to an external service

The structured JSON logging (PR 3) provides enough observability for the current operational context:
- Each scan failure emits a `level=ERROR` log event with `scan_id`, `job_id`, and a redacted error string
- Slack alerts fire when `MAX_RETRIES` is exceeded, surfacing unrecoverable failures to the team
- Sensitive credentials, auth headers and finding content must be excluded from alerts. The orchestrator invokes `_redact_sensitive_text`; actual boundary enforcement requires the canary and alert verification in the current implementation plan.

Self-hosted GlitchTip is the deferred alternative if Slack alert volume grows unmanageable or stack-trace deduplication becomes necessary. These are the conditions for reconsidering this decision; no external error-tracking service is enabled by that possibility.

## Consequences
No per-error stack traces in a dedicated UI. Triage requires `grep` or structured log queries on container stdout. This is acceptable until log query tooling is in place.
