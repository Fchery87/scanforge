# Managed beta implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver the confirmed managed security-operations beta with trustworthy source attribution, scanner evidence, tenant authority, finding history, and demonstrated recovery.

**Architecture:** Keep the shared Next.js/FastAPI/PostgreSQL control plane and organization-specific Redis Streams. Each organization has a host-service coordinator on a dedicated Linux VM with disposable offline scanner containers. Database-owned dispatch, fenced attempts, validated immutable evidence, and ordered observations govern scan outcomes; optional capabilities remain disabled until their separate gates pass.

**Tech stack:** Existing Next.js/React/TypeScript/Zod, FastAPI/Pydantic, SQLAlchemy/Alembic/PostgreSQL, Redis Streams, S3-compatible object storage, GitHub App, Linux/container runtime, and seven registered scanners.

**Status:** Not started. Confirmed design, not verified implementation.

**Authority:** [Confirmed Q1–Q54 and finding dispositions](../reviews/2026-10-16-roadmap-grilling.md), ADR-010 through ADR-017, and CONTEXT.md. This plan replaces conflicting execution scope/order in earlier readiness plans; preserve their historical receipts and verify any reused work. It does not authorize infrastructure purchases, customer onboarding, production deployment, destructive drills, merges, or external messages.

## Baseline and execution rules

- Planning observed `main` at `60621705b9307553430490aa364d778f503bfde2`; recheck before execution. The Git root is the parent `scanforge` directory, while this project is `scanforge-security-platform`.
- The working tree contains these planning documents and pre-existing changes in `apps/web/next-env.d.ts` and local tool state. Preserve unrelated work. The confirmed [cleanup record](../reviews/2026-10-16-cleanup-decisions.md) separately permits removal of the inspected empty `.cache/scanforge-recovery` scratch repository and retirement of the clean nested checkout while retaining its branch/history. Work in an isolated implementation checkout after preserving the confirmed documents; do not reset or clean the shared tree.
- Read the installed skills relevant to each task, particularly TypeScript, PostgreSQL, debugging and verification. Use regression-first development for demonstrated defects. No production credentials in fixtures, commands, screenshots or receipts.
- Extend existing modules before creating parallel authorities. The lifecycle service owns scan creation/dispatch/retry meaning; services enforce access; adapters normalize scanner output; the API owns durable evidence.
- One migration writer selects actual next Alembic revisions. One owner edits shared completion/internal routes at a time. No fixed migration numbers are reserved here.
- For each task, first reproduce the intended failure, make the smallest coherent change, run focused checks, inspect the diff, then commit only that task's explicit paths. Record actual SHA and evidence after verification; never invent them.
- Each checkbox is one action. Larger implementation steps must be split by the named invariant into small regression/fix/check/commit cycles. Do not implement all phases as one diff.
- `Done` requires the named evidence. A missing service is unverified, never a pass. Required PostgreSQL locking, real scanner execution, provider integration and browser scenarios cannot be substituted with mocks.
- Proposed new test and source paths below do not yet exist. Create tests before adding them to release gates. Existing tests are supporting evidence, not proof of the new contracts.

## Dependency tracker

### Preserved security acceptance details

These requirements were retained from the superseded August beta specification during the confirmed directory cleanup. They supplement the accepted October design; their presence is not proof of implementation.

| Requirement | Task / verification boundary |
| --- | --- |
| JWT verification requires configured issuer and audience | M02: reject missing/mismatched claims and missing customer-environment configuration; test actual auth entry points |
| Coordinators receive no database or storage-account credentials | M04: inspect host service environment and scanner boundary; all durable DB/object authority flows through API |
| Authenticated clones use the verified canonical GitHub origin | M06: reject arbitrary stored clone URLs, redirects and unverified provider identity before issuing clone authority |
| Audit actor context is request-local, never process-global | M02: concurrent requests cannot exchange actors or organizations |
| Project audit queries return only that project's events | M02/M12: cross-project and cross-organization read tests |
| Worker-originated mutations identify their worker actor | M02/M08/M09: persisted events record verified principal/attempt rather than impersonating a user |

Before commercial launch, review privacy/support/subprocessor disclosures and trust evidence. This is a later launch prerequisite, not an added initial-beta feature. Old unmeasured five-minute start, ten-minute recovery and numerical cohort-expansion promises are retired; M15 establishes measured operating guarantees.

| ID | Deliverable | Depends on | State | SHA / evidence |
| --- | --- | --- | --- | --- |
| M00 | Preserve baseline and isolate fixtures | None | Done | `5ba4ad5` (API 202p/8s, worker 122p, web node 76p, vitest 9p/1t, PG R04 10p/0s, Redis 1p/0s, S3 fixture pass) |
| M01 | Disable deferred/unsafe surfaces | M00 | Done | `82e116b` (`test_beta_capability_contract.py` 18p, worker AI boundary 14p, web node 76p, OpenAPI parity 2p) |
| M02 | Service access and transactional audit | M00 | Done | `f24ad50` (M02 auth/audit/membership/security suites 45p, OpenAPI parity 2p) |
| M03 | Versioned execution/evidence domain | M00 | Done | `1985b9a` (M03 contract/queue suites 17p, OpenAPI parity 2p, Alembic `0024`) |
| M04 | Safe host coordinator and runtime | M03 | Done | `7ca87e4` (34p/1s host/runtime/containment; live Docker container skipped on docker-free host) |
| M05 | Real scanner commands, safe parsing and redaction | M04 | In progress | Pending |
| M06 | Immutable repository/ref identity | M02, M03 | Not started | Pending |
| M07 | Durable dispatch and trigger identity | M03, M06 | Not started | Pending |
| M08 | Attempt fencing, cancellation and cleanup | M02, M04, M07 | Not started | Pending |
| M09 | Immutable artifacts and atomic completion | M02, M05, M08 | Not started | Pending |
| M10 | Finding identity, ordering and human decisions | M06, M09 | Not started | Pending |
| M11 | Verified GitHub ingress and reconciliation | M02, M06, M07, M08 | Not started | Pending |
| M12 | Required browser workflows and honest counts | M01, M02, M09, M10, M11 | Not started | Pending |
| M13 | Revocation, erasure and tombstone-aware restore | M02, M08, M09 | Not started | Pending |
| M14 | Legacy migration and contract cutover | M03, M08, M09, M10, M13 | Not started | Pending |
| M15 | Capacity, operations and staged release dossier | M04–M14 | Not started | Pending |

M02/M03 and M04/M06 can be investigated independently, but serialize shared file and migration edits. M12 may develop against accepted contracts before its dependencies finish; integration acceptance waits for real services.

## Task M00: Preserve baseline and build disposable test fixtures

**Files:** Inspect `Makefile`, `../.github/workflows/ci.yml`, `scripts/private_beta_gate.py`, both Python `pyproject.toml` files and `apps/web/package.json`. Create `infra/testing/docker-compose.integration.yml` and `scripts/verify_test_inventory.py` if the existing setup cannot support the required services.

- [x] Capture Git root/branch/HEAD, tracked diff and untracked names without reading secrets; preserve the confirmed docs and unrelated changes before isolating implementation.
- [x] Run the existing API, worker, Node and Vitest suites separately with bounded execution. Record collection, skips, failures and stalls rather than importing old pass claims.
- [x] Provide disposable PostgreSQL, native Redis, object storage and Linux container-host fixtures. Separate fixture credentials and isolated namespaces from customer services.
- [x] Verify collection of `apps/api/tests/test_r04_postgres_completion_red.py` with `R04_POSTGRES_URL` and `apps/worker/tests/test_redis_stream_recovery_integration.py` with `REDIS_URL`. Existing native Redis primitives do not prove the REST consumer path; provision a faithful adapter/service test later.
- [x] Commit fixture/inventory changes only after a reproducible local run; preserve baseline receipt with actual commands and identities.

**Check:** `make test` from the project root, plus explicit integration invocations after fixture setup. Expected: honest counts; unavailable required integrations are flagged. No blanket environment loading or mutation of a production database.

## Task M01: Disable deferred capabilities and prevent hidden backend execution

**Modify:** `apps/web/lib/dashboard-navigation.ts`, affected dashboard pages, `apps/web/lib/api.ts`, `apps/api/app/api/v1/router.py`, `apps/api/app/api/v1/routes/{exports,suppression_rules,scan_schedules,scorecard,webhooks}.py`, and `apps/worker/app/services/ai_investigation/stage.py`.

**Tests:** Extend `apps/api/tests/test_dashboard_routes_rbac.py`, `apps/api/tests/test_internal_scheduled_scans.py`, `apps/web/lib/dashboard-navigation.test.ts`; create `apps/api/tests/test_beta_capability_contract.py`.

- [x] Write failures proving AI, PR execution/publication, export generation, suppression automation, scheduling, grades, numeric scores and enforcement cannot execute in initial beta.
- [x] Run `.venv/bin/python -m pytest tests/test_beta_capability_contract.py -q` from `apps/api`; confirm the relevant unsupported behavior is reproduced.
- [x] Add one explicit server-side beta capability policy and align UI visibility. Preserve safe historical read behavior where it is supported; unsupported operations return a documented unavailable response without side effects.
- [x] Test disabled operations at their direct routes and trigger paths, not just hidden links. Keep manual full scans, automatic default-branch push scans and required triage enabled.
- [x] Run focused API/web tests, inspect the diff and commit the capability slice (`82e116bdb79dad20aec1432cbd2a0d422c85dd21`).

**Evidence:** Direct requests produce no jobs or mutations; browser presents only the accepted release promise. B7/B9/B10/B12/P1–P4 receive deferral, not fake fixes.

## Task M02: Authorize target resources before writes and persist audit atomically

**Modify:** `apps/api/app/services/{access_policies,organizations,memberships,users,findings,audit_logs,worker_identities}.py`, `apps/api/app/middleware/{auth,audit,service_auth}.py`, relevant routes and membership schemas. Add invitation and owner-transfer records through an inspected Alembic revision when needed.

**Tests:** Extend `test_authorization_regressions.py`, `test_route_integration_authorization.py`, `test_internal_service_org_boundaries.py`, `test_worker_identity_auth.py`; create `apps/api/tests/test_transactional_audit.py` and `apps/api/tests/test_membership_lifecycle.py`.

- [x] Reproduce privileged-org-A/viewer-org-B finding mutation and prove current denial occurs after the write. Add direct-service variants.
- [x] Implement the ADR-015 matrix with verified resource scope, active-user/member/worker checks and no admin shortcut for owner-only operations.
- [x] Move sensitive audit writes into the same transaction as domain mutations; make services composable without hidden intermediate commits. Reject stale revisions and roll back a bulk operation on any unauthorized/stale item.
- [x] Add verified pending invitations and atomic owner transfer. Keep operator worker credentials outside ordinary tenant administration.
- [x] Run focused route/service tests and audit-failure injection; commit each invariant separately (`f24ad50c86cea554f8bf1f01511a0e6705ba4f68`).

**Check:** From `apps/api`, `.venv/bin/python -m pytest tests/test_authorization_regressions.py tests/test_transactional_audit.py tests/test_membership_lifecycle.py -q` after creating new tests. Expected: every role/target combination explicit; denial/audit failure leaves zero mutations.

## Task M03: Define authoritative versioned execution and evidence contracts

**Modify:** `apps/api/app/schemas/{scans,scan_completion,canonical_findings}.py`, `apps/api/app/db/models/{scan,repository,finding,artifact}.py`, both `app/contracts/queue.py` modules, `apps/api/app/db/enums.py`. Create `apps/api/app/services/evidence_contract.py` and matching worker DTOs without duplicating authority.

**Tests:** Extend `apps/api/tests/test_canonical_finding_candidates.py`, both queue-contract suites; create `apps/api/tests/test_evidence_contract.py`.

- [x] Write fixtures for full/partial/unknown coverage, explicit scanner outcomes, immutable revision/provenance, cleanup pending and superseded unstarted work.
- [x] Define required and forbidden fields, contract negotiation, deterministic collection identities and server-owned derived values. Include artifact availability separately from scanner coverage.
- [x] Inspect Alembic heads and add additive records for identities, obligations, provenance, revisions and receipts. Use domain-specific types rather than generic JSON authority flags.
- [x] Test supported/unsupported versions and duplicate/unknown scanners. Design bounded ingress against candidate limits without claiming G1 capacity approval.
- [x] Generate OpenAPI and client types, review the diff and commit the schema/contract slice (`1985b9a465dc0d04d3c3eb7c9815f8fbcba924b2`).

**Check:** Existing `apps/api/scripts/emit_openapi.py`, `npm run gen:types` from `apps/web`, and focused contract tests. Exact canonical sorting details are engineering specifications constrained by Q42, not new product choices.

## Task M04: Implement the host executor and bounded workspace lifecycle

**Modify:** `apps/worker/app/runtime/{base,docker,containment,models}.py`, `apps/worker/app/worker/main.py`, `apps/worker/app/services/scan_pipeline/execution.py`, worker deployment templates and `render.yaml`. Create `infra/worker/scanforge-worker.service`, `scripts/provision_worker_host.sh`, and `apps/worker/tests/test_host_executor_integration.py`.

- [x] Reproduce missing Git/runtime, inaccessible UID/mount paths, production local fallback and unbounded output collection with disposable fixtures.
- [x] Run a supervised host coordinator with fixed organization identity, controlled workspace root, one scan and local runtime. Fix ownership for source/output mounts without broadening permissions to other tenants.
- [x] Require contained customer execution in all customer-facing environments. Stream bounded stdout/stderr, enforce output/workspace quotas and give the orchestrator explicit process/container cancellation handles.
- [x] Inspect the real host/container for no scanner credentials/network/socket, read-only source, bounded memory/process/disk and stopped descendants on timeout/cancel.
- [x] Record real runtime identity and hostile-fixture evidence, then commit deployment/runtime changes (`7ca87e493bdf4c8668d9d3a2303d52b31373aff6`). Do not purchase or deploy a customer host in this task.

**Check:** From `apps/worker`, `.venv/bin/python -m pytest tests/test_docker_runtime.py tests/test_runtime_containment.py tests/test_host_executor_integration.py -q` after creating the live suite. Live requirements fail or remain unverified when the runtime is unavailable.

## Task M05: Make every shipped scanner execute and preserve redacted findings

**Modify:** `apps/worker/app/scanners/{base,registry,trivy,gitleaks,osv,semgrep,syft,checkov,grype}.py`, normalizers, `app/security/secret_evidence.py`, `app/services/scan_pipeline/{execution,normalization}.py`, `apps/worker/Dockerfile.scanners`.

**Tests:** Extend `test_scanners.py`, `test_normalizers.py`, `test_secret_boundaries.py`; create `apps/worker/tests/test_real_scanner_fixtures.py` and sanitized fixtures under `apps/worker/tests/fixtures/scanners/`.

- [x] Add a regression proving Gitleaks evidence survives the actual execution/upload/normalization order and Trivy sanitization is idempotent with preserved rule/location.
- [x] Make missing contained commands/parsers fail explicitly. Implement one adapter at a time against positive, empty, malformed, truncated and timeout reports from the pinned executable.
- [x] Normalize safe evidence before discarding raw secret data. Retain outputs through upload/persistence, then clean them. Sanitize other reports for canary leakage; do not persist source-bearing artifacts unchecked.
- [x] Obtain versions/rules/database identity from the executing image manifest, refresh offline assets through trusted builds, and enforce freshness. Keep severity/confidence separate and preserve conflicting provider values.
- [x] Run the real image fixtures per scanner, inspect artifacts/logs/egress for canaries, then commit each adapter and shared-boundary slice (`d567a36667bce74db0bb8be34be778132094ce60`).

**Check:** `.venv/bin/python -m pytest tests/test_normalizers.py tests/test_secret_boundaries.py tests/test_real_scanner_fixtures.py -q` from `apps/worker`. A removed unready scanner requires explicit advertised/expected-coverage adjustment; no version-only pass is accepted.

## Task M06: Verify repository authority, exact revisions and branch continuity

**Modify:** `apps/api/app/services/{github,repositories,scans}.py`, repository/ref models, `apps/api/app/api/v1/routes/{github,repositories,internal}.py`, `apps/worker/app/services/scan_pipeline/{context,execution}.py`. Create `apps/api/app/services/repository_refs.py` and `apps/api/tests/test_repository_ref_identity.py`.

- [x] Add foreign-installation, unverified-binding, rename, transfer, queued branch movement, inaccessible SHA, force-push and branch-recreation fixtures.
- [x] Verify connecting GitHub user's installation access; bind installation to one organization and repository to one project using immutable provider IDs before uniqueness reservation.
- [x] Resolve exact revision/full ref/generation/coverage policy before dispatch. Reauthorize access and checkout/verify exact SHA without substituting branch tip. Preserve full ref names and generation evidence.
- [x] Establish provider-backed ancestry receipts; unknown/non-descendant continuity starts a new generation and never grants absence credit. Keep default and manually requested branch scope explicit.
- [x] Run real Git fixture and provider-contract tests, inspect authority denial and unchanged histories, then commit the identity slice (`c79090a54af35f9b0ef0f0c80e3938b3d34c1ad1`).

**Check:** `.venv/bin/python -m pytest tests/test_repository_ref_identity.py tests/test_execution_context_identity.py -q` from `apps/api`; worker checkout integration uses a local Git fixture plus non-production GitHub verification before release.

## Task M07: Persist dispatch obligations and account for every accepted trigger

**Modify:** `apps/api/app/services/{scans,scan_lifecycle}.py`, scan/webhook models, API queue client and webhook routes; worker queue contracts/client. Create `apps/api/app/services/scan_dispatch.py`, `apps/api/app/db/models/scan_dispatch.py`, and `apps/api/tests/test_scan_dispatch.py`.

- [ ] Inject a queue outage after scan creation and a crash after queue delivery before acknowledgement of dispatch.
- [ ] Persist accepted trigger, scan and dispatch obligation in one transaction. Implement an idempotent leased dispatcher with retries and visible awaiting-dispatch state.
- [ ] Define equivalent automatic business identity including immutable scope/coverage context. Separate manual request idempotency from deliberate reruns.
- [ ] Bound admission and implement explicit supersession of unstarted automatic work by newer descendants within the same generation. Retain every accepted outcome and skipped coverage; never coalesce manual or running work implicitly.
- [ ] Test concurrent dispatchers/duplicates/restarts/bursts and commit after one authoritative scan per equivalent trigger and zero stranded obligations are proven.

**Check:** `.venv/bin/python -m pytest tests/test_scan_dispatch.py tests/test_scan_lifecycle.py tests/test_webhook_route_security.py -q` from `apps/api`, with real database concurrency for obligation claims and actual queue-path integration.

## Task M08: Fence attempts and make terminal cleanup durable

**Modify:** API `services/{scan_lease,scans,scan_completion}.py`, `routes/internal.py`, worker `services/{lease_renewer,scan_orchestrator}.py`, `worker/{main,maintenance}.py`, runtime handles and queue client. Create `apps/api/tests/test_attempt_fencing.py` and `apps/worker/tests/test_cleanup_recovery.py`.

- [ ] Test stale/disabled/replacement principals at progress, findings, scanner updates, uploads/finalization, heartbeat and completion, not only final completion.
- [ ] Bind principal/incarnation/attempt/revision/live lease; prevent context refetch from silently adopting successor write authority. Queue reclaim cannot start scanners independently.
- [ ] Serialize cancellation/completion; persist cleanup obligations and receipts. Stop process groups/containers and verify source/output removal before queue acknowledgement.
- [ ] Recover after crashes at each decision/kill/receipt/ack boundary; an unreachable prior host blocks successor execution until stopped or fenced. Handle terminal failure cleanup as durably as cancellation/completion.
- [ ] Classify retryable execution failures, isolate notification delivery, and prove accepted completion never regresses after response/notification loss. Commit the lifecycle slices with actual recovery evidence.

**Check:** API `.venv/bin/python -m pytest tests/test_attempt_fencing.py tests/test_scan_lease.py tests/test_r04_postgres_completion_red.py -q`; worker `.venv/bin/python -m pytest tests/test_cleanup_recovery.py tests/test_lease_renewer.py -q`. Use two PostgreSQL sessions and real process/container inspection.

## Task M09: Publish immutable artifacts and server-derived atomic completion

**Modify:** API `clients/r2.py`, `routes/{internal,scans}.py`, `services/scan_completion.py`, evidence/artifact models/schemas; worker `clients/r2.py` and `services/scan_pipeline/{execution,persistence}.py`. Create `apps/api/tests/test_artifact_finalization.py` and `apps/api/tests/test_canonical_completion.py`.

- [ ] Reproduce erased artifact references, foreign-key signing and forged worker summary completeness. Test duplicate JSON keys before Pydantic parsing loses that information.
- [ ] Separate attempt-scoped staging and immutable verified objects. Verify organization/scan/attempt/scanner, existence, size/checksum and redaction policy before publish; workers cannot overwrite accepted objects.
- [ ] Derive counts/completeness/lifecycle eligibility from trusted contract/evidence. Canonicalize validated sanitized payloads with explicit unordered sorting and reject unknown/duplicate/invalid input.
- [ ] Atomically commit database evidence, references, audit and receipt. Verify identical replay, conflicting replay, replacement receipt-read and denied historical writes. Preserve valid findings with explicit unavailable secondary artifacts.
- [ ] Test upload-success/database-rollback orphan cleanup, expiry and authenticated downloads; commit after recovery leaves no exposed unreferenced objects or false evidence claims.

**Check:** API `.venv/bin/python -m pytest tests/test_artifact_finalization.py tests/test_canonical_completion.py tests/test_artifact_upload_isolation.py tests/test_artifact_download_contracts.py -q`; worker `test_r2_client.py` and persistence integration. Use real disposable object storage for publication/overwrite/expiry behavior.

## Task M10: Implement ordered observations and reviewer decisions

**Modify:** API `services/{finding_lifecycle,findings}.py`, `db/models/finding.py`, `schemas/findings.py`, finding routes, normalizer fingerprints and candidate schemas. Create `apps/api/tests/test_ordered_findings_postgres.py` and `apps/api/tests/test_duplicate_lineage.py`.

- [ ] Turn accepted Q16–Q17/Q24–Q28/Q49–Q53 into explicit transition and comparability tables with failing cases. Presence between absences, same-SHA reruns, old generations and partial/incompatible runs cannot close findings.
- [ ] Persist ordered per-branch observations and obligations; serialize affected finding/group updates and human revisions. Two distinct comparable descendant absences close only satisfied scopes; scoped human fixes retain other exposure.
- [ ] Implement reason/expiry risk decisions, manual reopen checkpoints, no stale human overrides, and all-or-nothing bulk operations with service authorization.
- [ ] Version category fingerprints; preserve scanner occurrences/conflicts, verified package/advisory lineage and manifest/path data. Duplicate groups aggregate unresolved obligations without silently transferring dispositions.
- [ ] Test PostgreSQL races, risk expiry idempotency, vulnerable upgrades, duplicate target changes, retirement and low-activity closure explanations; commit separately verifiable lifecycle/identity slices.

**Check:** API `.venv/bin/python -m pytest tests/test_finding_lifecycle_policy.py tests/test_ordered_findings_postgres.py tests/test_duplicate_lineage.py tests/test_findings_disappearance_scope.py -q`. Mocks/SQLite do not satisfy ordering and lock acceptance.

## Task M11: Complete GitHub onboarding, single ingress and reconciliation

**Modify:** API `routes/{github,webhooks,repositories}.py`, `services/{github,repositories,onboarding}.py`, webhook receipt model; web GitHub callback and repository connection pages. Create `apps/api/tests/test_github_reconciliation.py`.

- [ ] Reproduce normal UI connection without repository integration and accepted push without queued work. Add a signed single-ingress fixture with immutable provider routing.
- [ ] Derive repository integration server-side from verified binding. Accept supported default-branch triggers through M07 only; ignored PR/deferred actions cannot poison later supported-event deduplication.
- [ ] Handle installation/repository removal, permission changes, rename/transfer/default-branch events and current authorization. Reconcile missed events/current head without fabricated intervening observations.
- [ ] Follow the full installation/connection/push/scan/triage path with a non-production GitHub App. Verify reinstall/revoke/outage/redelivery and authorized manual branches.
- [ ] Persist provider receipts and safe operational errors, regenerate contracts, then commit after real event-to-scan evidence exists.

**Check:** API `.venv/bin/python -m pytest tests/test_webhook_route_security.py tests/test_webhook_verification.py tests/test_github_reconciliation.py -q`; release requires real App delivery and browser observations beyond fixtures.

## Task M12: Align API clients and deliver required browser workflows

**Modify:** `apps/web/lib/{api,api-schemas,api-types,scans/lifecycle}.ts`, dashboard onboarding/repository/scan/findings/audit pages, API `router.py`, `routes/{findings,findings_trend,org_stats,scorecard}.py`. Create `apps/web/tests/beta-workflows.spec.ts` with an explicitly configured browser runner and isolated authenticated fixtures.

- [ ] Feed actual endpoint responses through runtime validators: nullable integration, events array, membership names, pagination, coverage, receipts and expiring downloads. Add an assembled-router trend regression.
- [ ] Generate types/validators where supported and keep real-response fixtures for handwritten schemas. Remove unsupported client claims instead of adding casts or synthetic fields.
- [ ] Implement distinct loading/empty/error/stale/partial/expired states and actionable mutation errors. Polling failures never silently become zero findings. UI capabilities reflect current access; server remains authoritative.
- [ ] Count open/reviewing/to_fix/not_observed as unresolved; show acknowledged risk/false positives separately, duplicate groups once, vulnerable lineage continuity and unknown coverage. Keep scores/grades hidden.
- [ ] Exercise production-built authenticated onboarding, scan/partial/cancel/cleanup, triage/expiry, audit and downloads, including keyboard/error handling; commit workflow slices after endpoint and browser evidence agree.

**Check:** `npm run test:node`, `npm run test:vitest -- --maxWorkers=1`, `npx --no-install tsc --noEmit --incremental false`, `npm run build` from `apps/web`, plus the newly configured authenticated browser command. Extend tests against the route-used finding drawer, not only the similarly named unused component.

## Task M13: Implement disconnect, archive and verified erasure

**Modify:** API organization/repository services and routes, worker cleanup/recovery, dispatch admission, storage lifecycle configuration and operator scripts. Create `apps/api/app/services/tenant_erasure.py`, `apps/api/tests/test_tenant_erasure.py`, and `scripts/rehearse_tenant_restore.py`.

- [ ] Prove current deletion cascades do not constitute complete deletion; test late queue/provider deliveries and valid tokens after revocation.
- [ ] Separate disconnect/archive from erasure, retaining unresolved history and explicit branch retirement. Owner-authorized erasure first blocks work, drains/quarantines obligations and revokes authority.
- [ ] Persist tombstones and progress across object/database/queue/log/host cleanup. Reapply tombstones before serving restored backups; keep tombstones free of unnecessary sensitive content.
- [ ] Verify sanitized artifact expiry at 90 days and maximum backup retention at 30 days on actual chosen services; show active-store versus backup-expiry completion separately.
- [ ] Rehearse with a disposable tenant, inspect every store and retained copy, then commit implementation and witnessed procedure. Customer erasure or destructive production drills need explicit authorization.

**Check:** API `.venv/bin/python -m pytest tests/test_tenant_erasure.py tests/test_membership_lifecycle.py -q` and the disposable restore rehearsal. Storage policy existence alone is insufficient evidence of enforcement.

## Task M14: Reconcile legacy data and execute a versioned cutover rehearsal

**Modify:** Alembic revisions after inspecting current heads, API/worker version negotiation, migration/rollback scripts and producer entry points. Create `apps/api/tests/test_beta_legacy_migration.py`.

- [ ] Build sanitized fixtures for every legacy status, missing provenance/reasons/expiry/targets, duplicate cycles, artifact references and unsupported producer version.
- [ ] Implement repeatable conservative migration preserving original history and labeling unsupported conclusions unverified; report preserved/reclassified/unresolved counts.
- [ ] Test empty install and representative upgrade twice. Drain/cancel old attempts and reject legacy writes without authorizing data through alternate endpoints.
- [ ] Rehearse rollback against new receipts and deletion tombstones; preserve evidence semantics even when binary rollback is impossible. Use a tested roll-forward recovery where schema/data cannot safely downgrade.
- [ ] Commit after reconciled counts, concurrency fixtures and disposable migration/restore receipts identify actual schema/source/worker/image versions.

**Check:** `.venv/bin/python -m pytest tests/test_beta_legacy_migration.py -q` from `apps/api`, Alembic single-head inspection, and `scripts/rehearse_migrations.sh` / `scripts/rehearse_rollback.sh` only after validating they target disposable resources.

## Task M15: Measure operating envelope and assemble release evidence

**Modify:** `scripts/private_beta_gate.py`, `scripts/r12_queue_recovery_drill.py`, `scripts/r12_rollback_drill.py`, real root `../.github/workflows/ci.yml`, monitoring/host configuration and deployment records.

- [ ] Repair release-test inventory to actual files and environment variables. Add existing/new suites only after their collection and service requirements are proven. Required skipped integrations fail readiness.
- [ ] Measure sanitized representative repositories and maximum accepted payloads under simultaneous organization completions. Record host/cost proposal, memory/disk/CPU, transaction p95, scanner durations, backlog, rollback and hostile-input bounds; approve the final envelope rather than inherited candidate constants.
- [ ] Measure lease/renew/reclaim/kill/cleanup/retry/reconciliation/staging timing. Retain three total attempts, 120-second lease and 30-second renewal only if supported by results and operator approval.
- [ ] Name primary/backup operators and prove safe alert delivery, tenant stop, credential rotation, host fencing, recovery, erasure/restore and rollback. Maintain explicit business-hours support scope.
- [ ] Assemble Q47 dossier and original-finding dispositions with actual source/schema/worker/image IDs. Independently review unresolved defects, run a test-tenant deployment then one approved design partner, and expand only after explicit release/onboarding authorization.

**Check:** `python3 scripts/private_beta_gate.py --mode release --evidence-dir <verified-nonproduction-receipts>` after repairing the gate. Replace the placeholder with an actual reviewed directory, never a fabricated receipt. A clean full gate does not authorize deployment by itself.

## Verification and commit protocol

For each regression/fix slice:

1. Add the named scenario with real domain assertions: expected rows, authority denial, object ownership, process absence or browser-visible state. Avoid source-string tests as the main proof.
2. Run the focused test and capture the expected pre-fix failure. If prior work already fixes it, record adoption evidence and avoid gratuitous rewrites.
3. Implement the minimum coherent slice and run focused tests plus affected integration contracts.
4. Inspect `git diff --check`, `git diff --stat` and the actual diff. Record limitations and real environment identities.
5. Stage only enumerated task paths, commit a descriptive message, verify the SHA and attach evidence to the tracker. Do not stage unrelated planning/user changes automatically.

After schema/route changes, regenerate OpenAPI/client types and verify actual responses. Run the broader affected suites at phase integration; run all required release suites once on the candidate. Repeat only to resolve changed code, failures or concrete remaining risk.

## Deferred work is a separate enablement program

| Capability | Accepted contract | Entry gate |
| --- | --- | --- |
| Daily/weekly scheduling | Q38 | Reliable durable dispatch, measured capacity and recurrence/concurrency/downtime tests |
| Repository suppression | Q39 | Stable dispositions/counts; preview/matching/scope/expiry evidence |
| CSV/JSON exports | Q40 | Authorized consistent snapshots, generation jobs, redaction and safe expiring downloads |
| Advisory PR security review | Q41 | Exact head/base/merge-base, introduced/pre-existing distinction, fork access and retry-safe publication |
| Finding explanation | Q43–Q45 | Organization/provider consent, independent jobs, bounded budgets/cache and quality evaluation |
| AI code review | Q43–Q46, Q48 | Verified ephemeral context, untrusted-content isolation, held-out >=100-case evaluation, >=90% precision / >=80% recall for declared classes, approved latency/cost and shadow mode |

These tasks require their own detailed executable plans once prerequisites pass. PDF/custom cron/blocking enforcement/customer-hosted runners and broader project-sharing remain unavailable until separately designed. No deferred feature gets enabled merely because its module exists.

## Completion criterion

The plan is complete only when M00–M15 have actual verified evidence, every enabled original finding has passed acceptance, deferred capabilities are safely unavailable, and the operator has approved the measured operating envelope and staged release. Documentation acceptance, unit test counts, old plan statuses and this plan's existence cannot satisfy that criterion.
