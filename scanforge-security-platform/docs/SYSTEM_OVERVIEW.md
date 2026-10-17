# Current implementation architecture

This describes source present in the repository, including known defects. It does not certify a deployed installation. The accepted target architecture appears separately below; cleanup has not implemented it.

## Components and entry points

| Component | Source and responsibility |
| --- | --- |
| Next.js web | [App Router](../apps/web/app), [auth helpers](../apps/web/lib/auth), [token retrieval](../apps/web/lib/auth/api-token.ts), and [API client](../apps/web/lib/api.ts): browser workflows and authenticated API requests. |
| FastAPI | [main.py](../apps/api/app/main.py) installs middleware and mounts [v1 routes](../apps/api/app/api/v1/router.py) under `/api/v1`. [JWT middleware](../apps/api/app/middleware/auth.py) and [service authentication](../apps/api/app/middleware/service_auth.py) authenticate users and workers. |
| PostgreSQL | [SQLAlchemy models](../apps/api/app/db/models) and [Alembic migrations](../apps/api/alembic/versions): organizations, access, repositories, scans, findings, occurrences, decisions, and completion receipts. |
| Queue and worker | [Queue client](../apps/worker/app/clients/queue.py), [worker loop](../apps/worker/app/worker/main.py), and [orchestrator](../apps/worker/app/services/scan_orchestrator.py): organization-scoped Streams consumption, attempts, scanner stages, and completion calls. |
| Scanner execution | [Registry](../apps/worker/app/scanners/registry.py), [adapters](../apps/worker/app/scanners), [runtime selection](../apps/worker/app/runtime/base.py), and [Docker runtime](../apps/worker/app/runtime/docker.py). Registration is not proof of working contained analysis. |
| Object storage | [API R2 client](../apps/api/app/clients/r2.py) and [worker storage client](../apps/worker/app/clients/r2.py): scanner artifact transfer and signed downloads. |
| GitHub | [GitHub service](../apps/api/app/services/github.py), [connection routes](../apps/api/app/api/v1/routes/github.py), and [webhooks](../apps/api/app/api/v1/routes/webhooks.py): installation access, repository listing, and scan triggers. |

## Scan and finding flow

A manual request enters [scan routes](../apps/api/app/api/v1/routes/scans.py) and [lifecycle service](../apps/api/app/services/scan_lifecycle.py). The API stores the scan and attempts queue dispatch. The worker retrieves API-owned context, prepares a repository, runs adapters, handles artifacts, normalizes outputs, and sends completion evidence.

[Execution](../apps/worker/app/services/scan_pipeline/execution.py), [normalization](../apps/worker/app/services/scan_pipeline/normalization.py), and [persistence](../apps/worker/app/services/scan_pipeline/persistence.py) are separate stages. [API completion](../apps/api/app/services/scan_completion.py) commits evidence and a replay receipt. [Finding persistence](../apps/api/app/services/findings.py) distinguishes a canonical issue from scan occurrences; [lifecycle policy](../apps/api/app/services/finding_lifecycle.py) handles observations and dispositions.

The registry maps full scans to Trivy, Gitleaks, OSV, Semgrep, Syft, Checkov, and Grype; dependency scans to Trivy/OSV/Syft/Grype; diff scans to Gitleaks/Semgrep/Checkov; secret scans to Gitleaks. The following defects prevent treating that mapping as reliable coverage.

## Confirmed review gaps

These references preserve the original B1–B12 findings. Acceptance requirements and dispositions are in the [October decision record](reviews/2026-10-16-roadmap-grilling.md).

| Finding | Current implementation gap and source |
| --- | --- |
| B1 | [Adapter base](../apps/worker/app/scanners/base.py) defaults contained arguments to `--version`; OSV, Semgrep, Syft, Checkov, and Grype inherit that behavior instead of contained analysis. |
| B2 | [Artifact handling](../apps/worker/app/services/scan_pipeline/execution.py) clears Gitleaks data before normalization. [Secret sanitization](../apps/worker/app/security/secret_evidence.py) and [Trivy normalization](../apps/worker/app/normalizers/trivy.py) disagree on field names. |
| B3 | [Worker image](../apps/worker/Dockerfile) and [beta Compose](../infra/worker/docker-compose.beta.yml) do not establish the Git/container-runtime/workspace permissions required by the contained executor. |
| B4 | [Contained adapter cleanup](../apps/worker/app/scanners/base.py) removes output directories before later artifact upload uses their paths. |
| B5 | [Repository preparation and changed-file collection](../apps/worker/app/services/scan_pipeline/execution.py) clone a branch tip rather than verify the recorded commit and compare `HEAD~1` instead of the recorded PR base. |
| B6 | [Repository UI](<../apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx>) omits installation identity required by [connection persistence](../apps/api/app/services/repositories.py); push webhooks create scans without lifecycle enqueueing. |
| B7 | [GitHub Check payload builders](../apps/api/app/services/github_checks.py) lack a publication workflow; webhook response data is not a posted GitHub review. |
| B8 | [Handwritten client schemas](../apps/web/lib/api-schemas.ts) and [client methods](../apps/web/lib/api.ts) disagree with scorecard, nullable integration, and finding-event responses. |
| B9 | [Export schemas](../apps/api/app/schemas/exports.py), [service](../apps/api/app/services/exports.py), and dashboard disagree; no complete generation workflow connects pending requests to downloadable results. |
| B10 | [Suppression-rule CRUD](../apps/api/app/api/v1/routes/suppression_rules.py) stores rules without demonstrated ingestion enforcement; expiry is not persisted as requested. |
| B11 | [Router ordering](../apps/api/app/api/v1/router.py) lets dynamic finding detail shadow `/findings/trend`. |
| B12 | [Schedule service](../apps/api/app/services/scan_schedules.py) does not evaluate stored cron expressions or safely claim occurrences across concurrent schedulers. |

Additional release blockers include installation ownership verification, finding mutation authorization before commits, audit path matching, artifact ownership validation, temporal finding ordering, cancellation/containment limits, stale risk summaries, and mismatched release-gate test inventory. See the [finding dispositions](reviews/2026-10-16-roadmap-grilling.md) and [implementation tasks](plans/2026-10-16-managed-beta-implementation-plan.md). No current test-pass claim is implied here.

## AI and error handling

The [AI stage](../apps/worker/app/services/ai_investigation/stage.py) has [Anthropic](../apps/worker/app/services/ai_investigation/anthropic_provider.py) and [Ollama](../apps/worker/app/services/ai_investigation/ollama_provider.py) providers. `AI_ENABLED` defaults to false; private-beta policy prohibits enabling it. It explains existing normalized findings using metadata rather than independently reviewing repository code. The awaited stage and [fingerprint cache](../apps/worker/app/services/ai_investigation/cache.py) do not yet implement the accepted independent, versioned, tenant-scoped AI job design.

The API [global exception handler](../apps/api/app/main.py) logs exceptions and returns a generic internal error. [Generic error constants](../apps/api/app/core/error_messages.py), [error-sanitization regression tests](../apps/api/tests/test_error_sanitization.py), and the [advisory exception-handler checker](../apps/api/scripts/check_exception_handlers.py) exist. These mechanisms do not prove every error boundary is safe or that every audit event is durable.

## Accepted target, not implemented status

[ADR-010 through ADR-017](adr/) define a managed security-operations beta for three to five organizations: a dedicated Linux host per organization, supervised coordinator, isolated offline scanner containers, exact revision identity, durable dispatch, fenced attempts, ordered observations, immutable evidence, transactional authorization/audit, and verified cleanup.

Initial scope retains onboarding, manual full scans, automatic default-branch push scans, finding review/history/triage, assignment and due dates, honest coverage, and audit records. Scheduling, automated suppression, exports, grades/numeric scores, PR publication, and AI remain deferred until their separate requirements pass. Existing endpoints are not evidence that these features meet those requirements.

The [October plan](plans/2026-10-16-managed-beta-implementation-plan.md) owns execution order and required evidence. [CONTEXT.md](../CONTEXT.md) owns domain vocabulary. The [single setup guide](../RUNNING_LOCALLY.md) describes development; [runbooks](runbooks/) describe operator procedures. Historical September evidence remains linked from the [root index](../README.md).
