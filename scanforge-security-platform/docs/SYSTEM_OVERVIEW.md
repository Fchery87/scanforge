# Current implementation architecture

This describes source present in the repository, including known defects. It does not certify a deployed installation. Status entries were re-verified by source reading on 2026-11-04 at `main` `f5a47dd` unless marked otherwise; "source-verified" means the code was read, not that a deployed system was observed. Product direction is the [product charter](PRODUCT_CHARTER.md); execution order is the [redirection implementation plan](plans/2026-11-04-redirection-implementation-plan.md).

## Components and entry points

| Component | Source and responsibility |
| --- | --- |
| Next.js web | [App Router](../apps/web/app), [auth helpers](../apps/web/lib/auth), [token retrieval](../apps/web/lib/auth/api-token.ts), and [API client](../apps/web/lib/api.ts): browser workflows and authenticated API requests. |
| FastAPI | [main.py](../apps/api/app/main.py) installs middleware and mounts [v1 routes](../apps/api/app/api/v1/router.py) under `/api/v1`. [JWT middleware](../apps/api/app/middleware/auth.py) and [service authentication](../apps/api/app/middleware/service_auth.py) authenticate users and workers. |
| PostgreSQL | [SQLAlchemy models](../apps/api/app/db/models) and [Alembic migrations](../apps/api/alembic/versions) (head `0024`): organizations, access, repositories, scans, dispatch obligations, findings, occurrences, decisions, and completion receipts. |
| Dispatch | [Dispatch service](../apps/api/app/services/scan_dispatch.py) and [dispatch entry point](../apps/api/app/dispatch_main.py): durable obligations, leased claiming, automatic-scan supersession within a branch generation. |
| Queue and worker | [Queue client](../apps/worker/app/clients/queue.py), [worker loop](../apps/worker/app/worker/main.py), and [orchestrator](../apps/worker/app/services/scan_orchestrator.py): organization-scoped Streams consumption, attempts, scanner stages, and completion calls. |
| Scanner execution | [Registry](../apps/worker/app/scanners/registry.py), [adapters](../apps/worker/app/scanners), [runtime selection](../apps/worker/app/runtime/base.py), [Docker runtime](../apps/worker/app/runtime/docker.py), and [bounded streaming](../apps/worker/app/runtime/containment.py). |
| Object storage | [API R2 client](../apps/api/app/clients/r2.py) and [worker storage client](../apps/worker/app/clients/r2.py): presigned artifact transfer and signed downloads. Workers hold no storage-account credentials. |
| GitHub | [GitHub service](../apps/api/app/services/github.py), [connection routes](../apps/api/app/api/v1/routes/github.py), [repository refs](../apps/api/app/services/repository_refs.py), and [webhooks](../apps/api/app/api/v1/routes/webhooks.py): installation access, repository authority, exact revisions, and push-triggered scans. |

## Deployment topology (from configuration, not observed)

- [render.yaml](../render.yaml): the API web service, a weekly maintenance cron, and a per-minute `scanforge-scan-dispatch` cron. No worker or scheduler service runs on Render.
- Scanner execution runs on a dedicated Linux host per organization ([ADR-009](adr/ADR-009-dedicated-workers-for-private-beta.md), [ADR-011](adr/ADR-011-beta-executor-and-github-ingress.md)), supervised by [scanforge-worker.service](../infra/worker/scanforge-worker.service) and provisioned by [provision_worker_host.sh](../scripts/provision_worker_host.sh).
- The Next.js app deploys to Vercel ([notes](../infra/vercel/vercel-notes.md)). Redis Streams and R2 layouts are described in [infra](../infra).
- CI is the Git-root workflow `../.github/workflows/ci.yml`. The nested `.github/` (Dependabot/Renovate) is not at the repository root, and GitHub may not read it; this is unverified.

## Scan and finding flow

A manual request or default-branch push enters the [scan routes](../apps/api/app/api/v1/routes/scans.py) or webhooks and the [lifecycle service](../apps/api/app/services/scan_lifecycle.py). The API persists the scan and a dispatch obligation; the dispatcher enqueues it. The worker retrieves API-owned context, fetches and verifies the exact commit, runs adapters, sanitizes and uploads artifacts, normalizes outputs, and submits completion evidence.

[API completion](../apps/api/app/services/scan_completion.py) derives completeness and closure eligibility server-side ([evidence contract](../apps/api/app/services/evidence_contract.py)) and commits evidence with a replay receipt. [Finding persistence](../apps/api/app/services/findings.py) separates canonical findings from occurrences; [lifecycle policy](../apps/api/app/services/finding_lifecycle.py) records qualifying absences only for full scans with every expected scanner healthy and an analyzer comparable to the one that last observed the finding, and closes a finding after two distinct-commit absences on every observed branch.

## Trust boundaries

| Boundary | Enforced by | Status |
| --- | --- | --- |
| Tenant identity and authorization | API services and [access policies](../apps/api/app/services/access_policies.py); organization-scoped worker identities | Source-verified (M02) |
| Workers submit evidence, not decisions | Server-derived `closure_eligible`/coverage in the [evidence contract](../apps/api/app/services/evidence_contract.py) | Source-verified |
| Scanner process has no credentials | [Allowlisted environment](../apps/worker/app/security/proc_env.py) | Source-verified |
| Scanner container isolation | Digest-pinned image, `--network=none`, `--read-only`, dropped capabilities, `no-new-privileges`, non-root UID, pids/memory/tmpfs limits ([docker.py](../apps/worker/app/runtime/docker.py)); local runtime refused in customer environments ([base.py](../apps/worker/app/runtime/base.py)) | Source-verified; live container not exercised on 2026-11-04 |
| Source acquisition | `https://github.com` origin only, no redirects, no submodules, exact-SHA fetch and verify, private per-scan Git home, no host Git configuration, HTTPS-only transport ([execution.py](../apps/worker/app/services/scan_pipeline/execution.py), [proc_env.py](../apps/worker/app/security/proc_env.py)) | Source-verified. G4 and G5 fixed in P1.2; see the manual/scheduled SHA caveat under G5 |
| Optional AI | `AI_ENABLED` default false; server capability `ai_assistance` disabled; [ADR-017](adr/ADR-017-authoritative-evidence-and-optional-ai.md) | Disabled |
| Secret evidence | [Secret sanitization](../apps/worker/app/security/secret_evidence.py) before persistence; no secret values in fingerprints | Source-verified (M05) |

## Supported capability matrix

Server-side policy: [beta_capabilities.py](../apps/api/app/core/beta_capabilities.py). "Enabled" means reachable, not release-verified.

| Capability | State | Notes |
| --- | --- | --- |
| Manual full / dependency / secret scans | Enabled | Full scans run five scanners: Trivy (primary dependency engine), Syft (inventory), Gitleaks, Semgrep, Checkov. OSV-Scanner and Grype are registered and shipped in the scanner image but run only in explicit dependency scans ([ADR-019](adr/ADR-019-primary-dependency-engine.md), provisional: chosen without the corpus evaluation, which is NOT RUN) |
| Automatic default-branch push scans | Enabled | Via durable dispatch |
| Finding triage, history, assignment | Enabled | |
| PR review, diff scans | Disabled | Shadow review is the next milestone ([ADR-018](adr/ADR-018-developer-first-security-review-direction.md)) |
| FastAPI review pack (`fastapi.v1`) | Shadow PR runs only | Detection-gated context strategy: retrieval of identity/organization-scope dependencies plus three low-confidence Semgrep authorization/tenant-scope questions. Not comprehensive detection; unsupported cases are listed in `UNSUPPORTED_CASES` in [fastapi_pack.py](../apps/worker/app/review_packs/fastapi_pack.py). Pack id, version and rules digest are recorded in the run summary and the Semgrep scanner run metadata |
| Scheduled scans, exports, suppression rules | Disabled | Deferred |
| Grades, numeric risk scores, policy enforcement | Disabled | Deferred |
| AI assistance | Disabled | ADR-017 |
| Language/framework support matrix | Not yet published | Required by the charter before pilot claims |

## Review gap status

Original B1–B12 findings and their dispositions are in the [October decision record](reviews/2026-10-16-roadmap-grilling.md).

| ID | Original gap | Status 2026-11-04 |
| --- | --- | --- |
| B1 | Adapters ran `--version` instead of analysis | Fixed in source (M05, `d567a36`) |
| B2 | Gitleaks evidence cleared before normalization; field-name mismatch | Fixed in source (M05): sanitized output retained for normalization |
| B3 | Worker image lacked Git/runtime/workspace permissions | Addressed (M04): host coordinator plus provisioning script; live host not verified |
| B4 | Output directories removed before upload | Fixed in source (M05) |
| B5 | Branch tip instead of recorded commit; `HEAD~1` diff base | Exact-SHA fetch fixed (M06). Branch-tip fallback removed (G5, P1.2); the `HEAD~1` diff base remains; diff scans disabled |
| B6 | UI omitted installation identity; push scans not enqueued | Push enqueue fixed (M07 dispatch). UI path unverified (October M11/M12) |
| B7 | Check payloads without publication | Open; PR review disabled |
| B8 | Handwritten client schemas disagree with API | Open (October M12) |
| B9 | Export workflow incomplete | Open; exports disabled |
| B10 | Suppression rules not enforced at ingestion | Open; suppression disabled |
| B11 | `/findings/{finding_id}` shadows `/findings/trend` | Appears open: the findings router is included before the trend router and `finding_id` is a UUID path parameter ([router.py](../apps/api/app/api/v1/router.py)); runtime not verified |
| B12 | Schedules ignore cron expressions; unsafe concurrent claiming | Open; schedules disabled |

## Gaps found during the 2026-11-04 discovery

| ID | Gap | Source |
| --- | --- | --- |
| G1 | Fixed in source (P1.1, #33): an absence earns credit only when the scanner name, version, parser version, rules digest and fingerprint version match the analyzer that last observed the finding; otherwise an `absence_not_credited` event explains why. Residual risk: vulnerability-database (`db_digest`) and image changes are deliberately not compared, so an advisory withdrawal can still count as remediation until P1.5b. Was: a rules/parser/fingerprint-policy change could produce two absences and close a finding as `fixed` | [findings.py](../apps/api/app/services/findings.py) `mark_not_observed_after_scan`; [finding_lifecycle.py](../apps/api/app/services/finding_lifecycle.py) |
| G2 | Fixed in source for Semgrep, Checkov and Gitleaks (P1.5, #38; fp.v3, per-scanner policy versions in `SCANNER_FINGERPRINT_VERSIONS`): identity is repository + rule + path + normalized-snippet digest + occurrence index, with no line numbers and no secret-derived material. Existing fp.v2 findings are kept and never closed by fp.v3 absences (P1.1); they stay open as `analyzer_not_comparable` until re-observed, and re-observation creates a new fp.v3 finding (the successor link is #40). Was: Semgrep and Gitleaks fingerprints included line numbers; moved code created a new finding while the old one accrued absences | [identity.py](../apps/worker/app/normalizers/identity.py), [semgrep.py](../apps/worker/app/normalizers/semgrep.py), [gitleaks.py](../apps/worker/app/normalizers/gitleaks.py) |
| G3 | Partly addressed (P1.4, #37): default full scans no longer run OSV or Grype, so they stop producing duplicate dependency findings there; explicit dependency scans still run all three, and the fingerprint inputs are unchanged (fix is P1.5/#39). Was: Trivy, OSV and Grype share identical dependency fingerprint inputs without ecosystem or scanner, implicitly merging cross-scanner results (ADR-014 requires tested equivalence) | [trivy.py](../apps/worker/app/normalizers/trivy.py), [osv.py](../apps/worker/app/normalizers/osv.py), [grype.py](../apps/worker/app/normalizers/grype.py) |
| G4 | Fixed in source (P1.2, #34): git subprocesses get a private per-scan `HOME`, `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL=/dev/null`, no terminal prompts, hooks and fsmonitor disabled, LFS smudge skipped, and only HTTPS transport (file transport only in non-customer fixture mode). Was: host Git filters or URL rewrites could apply to untrusted checkouts | [proc_env.py](../apps/worker/app/security/proc_env.py) `build_git_env`, [execution.py](../apps/worker/app/services/scan_pipeline/execution.py) |
| G5 | Fixed in the worker (P1.2, #34): `prepare_repository` refuses a context with no exact commit SHA before any git or network activity, and the branch-tip clone path is removed. Caveat: the API does not resolve a SHA for manual or scheduled scans that omit `commit_sha` (only push webhooks carry `after`), so those scans now fail at the worker with an explicit error instead of scanning the branch tip. API-side resolution at scan creation is open work | [execution.py](../apps/worker/app/services/scan_pipeline/execution.py) `prepare_repository`; [scans.py](../apps/api/app/services/scans.py) |
| G6 | Absence requires every expected scanner healthy (five on a default full scan since P1.4, formerly seven), so one failing capability blocks reassessment of every capability | [finding_lifecycle.py](../apps/api/app/services/finding_lifecycle.py) `evaluate_scan_absence_evidence` |
| G7 | The AI stage is awaited inside the scan pipeline rather than a separate job (ADR-017); disabled | [scan_orchestrator.py](../apps/worker/app/services/scan_orchestrator.py) |

## Error handling

The API [global exception handler](../apps/api/app/main.py) logs exceptions and returns a generic internal error. [Generic error constants](../apps/api/app/core/error_messages.py), [error-sanitization tests](../apps/api/tests/test_error_sanitization.py), and the [advisory exception-handler checker](../apps/api/scripts/check_exception_handlers.py) exist. They do not prove every error boundary is safe or that every audit event is durable.

[CONTEXT.md](../CONTEXT.md) owns domain vocabulary. The [setup guide](../RUNNING_LOCALLY.md) describes development; [runbooks](runbooks/) describe operator procedures.
