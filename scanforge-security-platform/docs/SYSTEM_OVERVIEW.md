# System Overview

## Purpose

ScanForge is the orchestration layer around repository security scanners. It does not replace tools like Trivy, Gitleaks, OSV-Scanner, Semgrep, Syft, Checkov, or Grype. It manages repository onboarding, scan execution, normalized finding storage, triage workflow, risk and SLA signals, notifications, exports, scorecards, advisory policy feedback, and auditability.

The current product wedge is repository security operations for internal engineering and security teams. Centralized triage is the primary workflow. GitHub pull request feedback exists, but it is advisory rather than merge-blocking.

## Runtime Topology

- browser -> Next.js web app
- web app -> FastAPI API
- API -> Postgres for system-of-record data
- API -> Upstash Redis REST queue for scan jobs and transient job status
- API -> GitHub App APIs and verified webhooks
- API -> S3-compatible storage for artifact download redirects
- worker -> Upstash Redis REST queue
- worker -> internal API routes for scan coordination
- worker -> GitHub repository clone flow using API-issued credentials
- worker -> scanner binaries on disk
- worker -> S3-compatible object storage for raw outputs and artifacts

## Core Flow

1. A user creates or joins an organization.
2. The user creates a project.
3. The organization connects GitHub.
4. The user connects repositories to the project.
5. The API creates scan records and enqueues jobs through the scan lifecycle service.
6. The worker loads authoritative scan context from the API.
7. The worker clones the repository and runs the selected scanners.
8. The worker uploads raw artifacts and persists normalized findings.
9. The API updates finding lifecycle state, risk score, SLA preview, scanner health, and scorecard signals.
10. Users review findings, scans, schedules, notifications, exports, scorecards, audit logs, and advisory policy feedback in the web app.

## Scan Lifecycle

```text
queued -> running -> completed
                  -> failed
                  -> canceled
```

Manual scans, scheduled scans, webhook scans, and pull request scans use one lifecycle path. Queue payloads carry the scan identity only. The worker retrieves organization, project, repository, branch, commit, expected scanners, and coverage scope from the API.

Worker scan summaries record scanner health, seen fingerprints, scope, changed files, duration, and artifact references. A scan can complete while individual scanners fail; downstream finding lifecycle decisions consume scanner health instead of assuming scan status alone is enough.

The worker also tracks retry metadata and can move exhausted jobs to a dead-letter queue path after repeated failures.

## Current Scanner Coverage

- Trivy
- Gitleaks
- OSV-Scanner
- Semgrep
- Syft
- Checkov
- Grype

Scan modes determine which scanners run:

- `scan.repo.full`: Trivy, Gitleaks, OSV-Scanner, Semgrep, Syft, Checkov, Grype
- `scan.repo.diff`: Gitleaks, Semgrep, Checkov
- `scan.dependencies`: Trivy, OSV-Scanner, Syft, Grype
- `scan.secrets`: Gitleaks

## Finding Lifecycle

ScanForge distinguishes long-lived findings from scan-specific finding instances.

- `Finding`: durable deduplicated issue record
- `FindingInstance`: occurrence of that issue in a specific scan
- `FindingEvent`: user or system lifecycle event
- `FindingReference`: scanner or external reference URL

Finding workflow states are explicit: `open`, `reviewing`, `to_fix`, `accepted_risk`, `false_positive`, `duplicate`, `not_observed`, and `fixed`.

`not_observed` is a first-class state for findings absent from a later relevant scan without yet being proven fixed. Fixed promotion requires policy evidence, currently repeated not-observed evidence. Automatic state changes depend on scanner health and comparable coverage.

## Prioritization And Reporting

Risk score is a transparent 0-100 score derived from severity, scanner confidence, workflow state, and repository importance. Repository importance can be `critical`, `high`, `normal`, or `low`.

SLA preview is advisory and uses workflow state plus due date. Accepted risk, false positive, duplicate, and fixed findings are not applicable to SLA pressure.

Scorecards report exposure, trend direction, SLA pressure, scanner health, noisy scanner indicators, high-risk repositories or projects, and advisory policy results.

Policy evaluation is read-only and non-blocking. It can flag high average risk, overdue SLA work, or partial scanner health without blocking PRs or merges.

Remediation guidance is deterministic and based on finding evidence, package/version data, and references. It does not perform AI remediation or create automatic patches.

## Core Data Relationships

```text
User
  -> OrganizationMember
  -> Organization
  -> Project
  -> Repository
  -> Scan
  -> ScannerRun
  -> Finding
  -> FindingInstance / FindingEvent / FindingReference
```

Repository integrations attach GitHub installation metadata to repositories. Scan schedules create scheduled scan lifecycle outcomes. Webhook deliveries preserve GitHub webhook replay and processing metadata. Exports and scan artifacts expose generated or raw data through storage-backed download flows.

## Operational Notes

- Auth is JWT-based and wired for Neon Auth claims verification.
- Internal worker routes are protected with `INTERNAL_API_KEY` service auth.
- Artifact downloads are exposed through presigned URLs generated by the API.
- Queue communication assumes Upstash Redis REST semantics rather than raw Redis TCP.
- GitHub is the primary SCM integration; GitLab and Bitbucket are intentionally deferred.
- Pull request workflow is advisory only; hard merge blocking is intentionally deferred.

## Related Docs

- `../README.md`
- `development-setup.md`
- `scanner-setup.md`
- `adr/ADR-004-finding-lifecycle-policy.md`
- `plans/2026-05-02-module-first-security-operations-roadmap.md`
