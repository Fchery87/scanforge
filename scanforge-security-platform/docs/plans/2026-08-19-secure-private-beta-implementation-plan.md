# Secure Private Beta Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make ScanForge safe and reliable enough to operate a three-organization private beta with dedicated workers and disposable scanner containers.

**Architecture:** Keep the web application, API, PostgreSQL, GitHub webhook receiver, and scheduler shared. Route each organization's scans through an organization-specific Redis Stream to a dedicated worker host. The worker coordinator holds organization-scoped authority and runs scanner commands inside credential-free disposable containers. The API commits scan evidence and final status atomically.

**Tech Stack:** Next.js 16, FastAPI, SQLAlchemy, PostgreSQL 16, Alembic, Redis Streams through Upstash REST, Docker, Cloudflare R2 compatible storage, GitHub Apps, Pytest, Vitest, Playwright, and GitHub Actions.

**Specification:** `spec/SECURE_PRIVATE_BETA.md`

**Architecture decision:** `docs/adr/ADR-009-dedicated-workers-for-private-beta.md`

## Execution rules

- Use `@superpowers:test-driven-development` for every behavior change.
- Use `@superpowers:systematic-debugging` for the hanging API suite and any unexplained failure.
- Use `@sandbox-sdk` as a security checklist for the scanner-runtime boundary. The beta implementation uses local Docker containers, not Cloudflare Sandbox.
- Complete tasks in order. Do not start a later quality gate while an earlier gate is red.
- Keep AI investigation disabled throughout the beta.
- Commit after each task. Do not combine gate-closing changes with market features.
- Run the task's focused tests before the full gate command.

## Phase 0: restore trustworthy release evidence

### Task 1: Repair the test and dependency baseline

**Files:**

- Modify: `apps/web/vitest.config.ts`
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/tests/test_internal_routes.py`
- Modify: `.github/workflows/ci.yml`
- Test: all existing `apps/web/**/*.test.ts` and `apps/web/**/*.spec.tsx` files

**Step 1: Prove the web test selection bug**

Run:

```bash
cd apps/web
npm test
```

Expected: one file and three tests run even though the repository contains additional `*.test.ts` files.

**Step 2: Include both test naming conventions**

Set the Vitest include list to:

```ts
include: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}"],
exclude: ["node_modules", ".next"],
```

Run `npm test`. Expected: all web unit tests run. Fix real failures. Do not exclude failing tests.

**Step 3: Remove known critical and high web advisories**

Run:

```bash
cd apps/web
npm install @neondatabase/auth@latest
npm audit --audit-level=high
npm run build
```

Expected: the audit has no critical or high advisory. If the current Neon package cannot meet that gate, replace the beta authentication adapter before continuing.

**Step 4: Repair API type discovery**

Add `explicit_package_bases = true` under `[tool.mypy]`. Run:

```bash
cd apps/api
.venv/bin/mypy app
```

Expected: MyPy checks the application instead of stopping on duplicate module discovery. Fix the errors it reports.

**Step 5: Diagnose the hanging API test process**

Run the internal-route file with `PYTHONASYNCIODEBUG=1`, Pytest timeout diagnostics, and one test at a time. Fix the unclosed application, HTTP client, database engine, or background task at its owner. Add a regression that fails if teardown leaves a pending task.

Run:

```bash
cd apps/api
DATABASE_URL=sqlite+aiosqlite:///:memory: PYTHONASYNCIODEBUG=1 .venv/bin/python -m pytest tests/test_internal_routes.py -vv
```

Expected: the process exits after the result summary.

**Step 6: Make CI cover shared release files**

Add the root `render.yaml`, `Makefile`, `docker-compose.yml`, `infra/**`, `spec/**`, `docs/adr/**`, and shared contract files to the relevant path filters. Replace the SQLite-only API test job in later Task 11. Keep this task focused on test selection.

**Step 7: Verify and commit**

Run:

```bash
make lint
make test
make web-build
```

Commit:

```bash
git add apps/web apps/api/pyproject.toml apps/api/tests/test_internal_routes.py .github/workflows/ci.yml
git commit -m "test: restore private beta release coverage"
```

## Phase 1: Gate 1, evidence integrity

### Task 2: Add organization-scoped worker identities

**Files:**

- Create: `apps/api/app/db/models/worker_identity.py`
- Create: `apps/api/app/services/worker_identities.py`
- Create: `apps/api/app/schemas/worker_identities.py`
- Create: `apps/api/scripts/manage_worker_identity.py`
- Create: `apps/api/alembic/versions/0017_worker_identities.py`
- Modify: `apps/api/app/db/models/__init__.py`
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/middleware/service_auth.py`
- Modify: `apps/api/app/api/v1/routes/internal.py`
- Test: `apps/api/tests/test_worker_identity_auth.py`
- Test: `apps/api/tests/test_internal_routes.py`

**Step 1: Write failing identity tests**

Cover these cases:

- A valid credential returns a principal with `worker_id` and `organization_id`.
- An unknown, disabled, or malformed credential returns 401.
- An unset worker-auth configuration returns 503.
- A worker for organization A cannot read or mutate a scan in organization B.
- The database stores only a credential hash.

Use a principal with this shape:

```python
@dataclass(frozen=True)
class WorkerPrincipal:
    worker_id: UUID
    organization_id: UUID
    capabilities: frozenset[str]
```

**Step 2: Run the focused tests**

Run:

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_worker_identity_auth.py tests/test_internal_routes.py -vv
```

Expected: tests fail because worker identities do not exist.

**Step 3: Add the model and migration**

Create `worker_identities` with `id`, `organization_id`, `name`, `credential_hash`, `capabilities_json`, `disabled_at`, `last_seen_at`, `created_at`, and `updated_at`. Index `organization_id` and make active names unique within an organization.

Hash credentials with HMAC-SHA256 and `WORKER_CREDENTIAL_PEPPER`. Generate 32 random bytes for each credential. Print the plaintext only once from the management script.

**Step 4: Replace global service authorization**

Make `require_service_auth` return `WorkerPrincipal`. Update every internal route to load the target resource, derive its organization, and compare it with the principal before reading or writing data.

Keep a separate scheduler credential or move due-schedule execution to a trusted cron route with its own capability. Do not give a customer worker permission to run every organization's schedules.

**Step 5: Verify and commit**

Run the focused tests, the API suite, and Alembic upgrade and downgrade on a disposable PostgreSQL database.

Commit:

```bash
git add apps/api
git commit -m "feat(api): add organization-scoped worker identities"
```

### Task 3: Replace the scan list with organization-specific Redis Streams

**Files:**

- Modify: `apps/api/app/contracts/queue.py`
- Modify: `apps/worker/app/contracts/queue.py`
- Modify: `apps/api/app/clients/queue.py`
- Modify: `apps/worker/app/clients/queue.py`
- Modify: `apps/api/app/services/scan_lifecycle.py`
- Modify: `apps/worker/app/worker/main.py`
- Modify: `apps/worker/app/worker/maintenance.py`
- Test: `apps/api/tests/test_queue_client.py`
- Test: `apps/api/tests/test_scan_lifecycle.py`
- Test: `apps/worker/tests/test_queue_client.py`
- Test: `apps/worker/tests/test_queue_contract.py`

**Step 1: Write failing stream-contract tests**

Require these keys:

```text
queue:scans:{organization_id}
queue:scans:{organization_id}:dlq
```

Require one consumer group named `scanforge-workers`. Use the scan ID as the job idempotency key. Test `XADD`, `XREADGROUP`, `XACK`, `XDEL`, `XPENDING`, and `XAUTOCLAIM` command shapes.

**Step 2: Run the focused tests**

Expected: failures show the current global list and `BRPOP` behavior.

**Step 3: Implement the API producer**

Change `QueueClient.enqueue` to require `organization_id`. Add `organization_id` to the queue namespace, not the payload authority. Update `ScanLifecycleService` so every manual and scheduled caller passes the organization derived from the repository's project.

**Step 4: Implement the worker consumer**

Require `WORKER_ORGANIZATION_ID` and `WORKER_CONSUMER_NAME` at startup. Refuse to start if either is empty. Read only the configured stream. Reclaim stale pending entries on every worker loop before reading a new message.

Move a message to the dead-letter stream before acknowledging and deleting the original. Requeue by leaving or reclaiming the pending message. Never delete recovery state first.

**Step 5: Add a Redis integration test**

Terminate a consumer after delivery but before acknowledgement. Start a second consumer, advance the idle timeout, and prove `XAUTOCLAIM` returns the original scan ID.

**Step 6: Verify and commit**

Run both queue suites and the scan lifecycle suite. Commit:

```bash
git add apps/api apps/worker
git commit -m "feat(queue): add durable organization scan streams"
```

### Task 4: Commit scan results and completion atomically

**Files:**

- Create: `apps/api/app/schemas/scan_completion.py`
- Create: `apps/api/app/services/scan_completion.py`
- Create: `apps/api/alembic/versions/0018_idempotent_scan_occurrences.py`
- Modify: `apps/api/app/api/v1/routes/internal.py`
- Modify: `apps/api/app/services/findings.py`
- Modify: `apps/api/app/db/models/finding.py`
- Modify: `apps/api/app/db/models/scan.py`
- Modify: `apps/worker/app/services/scan_pipeline/persistence.py`
- Modify: `apps/worker/app/services/scan_orchestrator.py`
- Test: `apps/api/tests/test_scan_completion.py`
- Test: `apps/api/tests/test_findings_scanner_integration.py`
- Test: `apps/worker/tests/test_scan_orchestrator.py`

**Step 1: Write failing completion tests**

Cover:

- A database failure leaves the scan incomplete.
- Repeating one completion request produces no duplicate finding instance or reference.
- A canceled scan returns 409 and remains canceled.
- Scanner health and findings commit with the final scan status.
- Finding disappearance runs only after the completion transaction has valid comparable scanner coverage.

Add `occurrence_fingerprint` to each canonical finding instance. Add a unique constraint on `scan_id` and `occurrence_fingerprint`.

**Step 2: Add one completion endpoint**

Create `POST /api/v1/internal/scans/{scan_id}/complete`. The request contains normalized findings, scanner-run outcomes, artifact references, and the completion summary. The service validates the worker principal and scan state, then performs one transaction.

Progress endpoints may update non-terminal stages. They cannot set `completed`, overwrite `canceled`, or mark findings not observed.

**Step 3: Make worker persistence fail closed**

Delete exception swallowing from `PersistenceStage.persist_findings`. Replace it with `complete_scan`. Call `queue.ack` only after the completion endpoint returns success. Treat timeouts and non-2xx responses as retryable failures.

**Step 4: Verify fault behavior**

Inject HTTP 500, connection timeout, commit failure, and duplicate delivery. Assert that no false completion or duplicate evidence occurs.

**Step 5: Verify and commit**

Run the focused API and worker suites. Commit:

```bash
git add apps/api apps/worker
git commit -m "fix(scans): make completion atomic and idempotent"
```

### Task 5: Make cancellation terminal and observable

**Files:**

- Modify: `apps/api/app/services/scans.py`
- Modify: `apps/api/app/api/v1/routes/scans.py`
- Modify: `apps/api/app/services/scan_completion.py`
- Modify: `apps/worker/app/services/scan_orchestrator.py`
- Test: `apps/api/tests/test_scans_service.py`
- Test: `apps/api/tests/test_scans_route_contract.py`
- Test: `apps/worker/tests/test_scan_orchestrator.py`

**Step 1: Write failing race tests**

Cancel a running scan, then deliver progress and completion calls. Require 409 from both terminal writes and preserve `canceled`.

**Step 2: Add worker cancellation checks**

Read authoritative scan state before clone, before scanner execution, before artifact upload, and before completion. Stop work and acknowledge the canceled job without publishing findings.

**Step 3: Verify and commit**

Run the three focused test files. Commit:

```bash
git add apps/api apps/worker
git commit -m "fix(scans): enforce terminal cancellation"
```

Gate 1 command:

```bash
make lint
make test
cd apps/api && .venv/bin/mypy app
```

Do not continue until Gate 1 passes.

## Phase 2: Gate 2, secret safety and containment

### Task 6: Remove secret values from every boundary

**Files:**

- Create: `apps/worker/app/security/secret_evidence.py`
- Modify: `apps/worker/app/normalizers/gitleaks.py`
- Modify: `apps/worker/app/normalizers/trivy.py`
- Modify: `apps/worker/app/services/scan_pipeline/execution.py`
- Modify: `apps/worker/app/scanners/gitleaks.py`
- Modify: `apps/worker/app/services/ai_investigation/stage.py`
- Modify: `apps/api/app/clients/r2.py`
- Modify: `apps/api/app/api/v1/routes/internal.py`
- Modify: `apps/worker/app/clients/r2.py`
- Modify: `infra/r2/lifecycle-rule.json`
- Test: `apps/worker/tests/test_normalizers.py`
- Test: `apps/worker/tests/test_secret_boundaries.py`
- Test: `apps/api/tests/test_findings_scanner_integration.py`

**Step 1: Add a canary secret fixture**

Use one generated value per test. Assert that the value does not appear in the normalized finding, instance evidence, serialized completion request, raw artifact, log capture, notification, or AI-provider stub.

**Step 2: Remove secret matches from normalizers**

Store the rule, type, path, line, and commit. Do not store the match or a value-derived preview. Compute canonical fingerprints from safe location and rule fields.

**Step 3: Sanitize artifact output**

Do not upload Gitleaks raw output. Remove `Match` and related value-bearing fields from Trivy secret sections before upload. Delete every temporary Gitleaks file in `finally`.

Change object keys to `scan-artifacts/{organization_id}/{scan_id}/...`. Keep the lifecycle prefix at `scan-artifacts/` and verify expiration on a staging object.

Add an internal route that issues an exact-key presigned upload URL after it verifies the worker principal, scan, organization, artifact type, and key prefix. Replace the worker's R2 account credentials with HTTP uploads to these URLs.

**Step 4: Disable AI for beta**

Reject `AI_ENABLED=true` when `APP_ENV=private-beta`. Keep the canary test even while AI is disabled.

**Step 5: Verify and commit**

Run the secret-boundary tests and scan normalizer tests. Commit:

```bash
git add apps/api apps/worker infra/r2/lifecycle-rule.json
git commit -m "fix(secrets): remove secret values from durable boundaries"
```

### Task 7: Restrict clone credentials to verified GitHub repositories

**Files:**

- Modify: `apps/api/app/api/v1/routes/internal.py`
- Modify: `apps/api/app/services/github.py`
- Modify: `apps/api/app/services/repositories.py`
- Modify: `apps/api/app/schemas/repositories.py`
- Modify: `apps/worker/app/services/scan_pipeline/execution.py`
- Test: `apps/api/tests/test_internal_routes.py`
- Test: `apps/api/tests/test_route_integration_authorization.py`
- Test: `apps/worker/tests/test_scan_orchestrator.py`

**Step 1: Write origin and ownership tests**

Reject manual, non-GitHub, wrong-organization, missing-installation, and installation-inaccessible repositories. Prove that a stored attacker URL is never returned with an authorization header.

**Step 2: Construct the clone target in the API**

Use `https://github.com/{owner_name}/{repo_name}.git` after validating both path segments and confirming installation access through GitHub. Do not use `Repository.clone_url` for authenticated beta scans.

**Step 3: Scope the credential to the clone operation**

Pass the header with command-scoped Git configuration. Clear it after clone. Reject redirects to a different origin and disable Git submodule recursion.

**Step 4: Verify and commit**

Run the focused API and worker tests. Commit:

```bash
git add apps/api apps/worker
git commit -m "fix(github): scope authenticated repository cloning"
```

### Task 8: Run scanner commands in disposable containers

**Files:**

- Create: `apps/worker/app/runtime/base.py`
- Create: `apps/worker/app/runtime/local.py`
- Create: `apps/worker/app/runtime/docker.py`
- Create: `apps/worker/app/runtime/models.py`
- Create: `apps/worker/Dockerfile.scanners`
- Create: `apps/worker/tests/test_docker_runtime.py`
- Modify: `apps/worker/app/scanners/base.py`
- Modify: all adapters under `apps/worker/app/scanners/`
- Modify: `apps/worker/app/services/scan_pipeline/execution.py`
- Test: `apps/worker/tests/test_scanners.py`

**Step 1: Define the runtime contract**

Use one request type with the executable, arguments, source directory, output directory, timeout, CPU limit, memory limit, process limit, and network policy. Return exit code, stdout, stderr, duration, and timeout state.

**Step 2: Write containment tests**

Prove that the Docker command uses a non-root user, `--read-only`, `--network=none`, `--cap-drop=ALL`, `no-new-privileges`, a PID limit, a memory limit, a CPU limit, a read-only source mount, and a writable output mount. Prove that no credential environment variable or Docker socket is mounted.

**Step 3: Build the pinned scanner image**

Pin the image by digest and pin every scanner version. Install vulnerability databases and rule sets at image build time. Emit a manifest with scanner and database versions.

**Step 4: Route adapters through `ScanRuntime`**

Keep `LocalScanRuntime` for unit tests and local development. Require `DockerScanRuntime` when `APP_ENV=private-beta`. Reject startup if Docker is unavailable or the scanner image digest is missing.

**Step 5: Test hostile fixtures**

Cover fork attempts, disk growth, timeout, oversized output, symlinks outside the source mount, and outbound connection attempts. Require containment and cleanup.

**Step 6: Verify and commit**

Run worker tests and the Docker containment suite on a Linux CI runner. Commit:

```bash
git add apps/worker
git commit -m "feat(worker): isolate scanner commands in containers"
```

Gate 2 command:

```bash
make lint
make test
docker build -f apps/worker/Dockerfile.scanners apps/worker
PYTHONPATH=apps/worker apps/worker/.venv/bin/pytest apps/worker/tests/test_secret_boundaries.py apps/worker/tests/test_docker_runtime.py -vv
```

Do not continue until Gate 2 passes.

## Phase 3: Gate 3, complete GitHub workflow

### Task 9: Route every trigger through the scan lifecycle

**Files:**

- Modify: `apps/api/app/api/v1/routes/webhooks.py`
- Modify: `apps/api/app/services/scan_lifecycle.py`
- Modify: `apps/api/app/services/scan_schedules.py`
- Modify: `apps/api/app/schemas/scan_schedules.py`
- Modify: `apps/api/app/schemas/scans.py`
- Create: `apps/api/alembic/versions/0019_pull_request_scan_context.py`
- Modify: `apps/api/app/db/models/scan.py`
- Test: `apps/api/tests/test_scan_lifecycle.py`
- Test: `apps/api/tests/test_webhook_route_security.py`
- Test: `apps/api/tests/test_internal_scheduled_scans.py`

**Step 1: Write trigger parity tests**

For manual, scheduled, push, and pull-request triggers, assert that `ScanLifecycleService` creates one scan and one organization-routed stream message.

**Step 2: Add pull-request execution context**

Persist `pull_request_number`, `base_sha`, and `head_sha` on the scan. Require them for diff scans created from a pull request.

Restrict beta schedules to the frequencies the scheduler implements. Reject custom cron expressions until the scheduler evaluates them correctly.

**Step 3: Remove direct scan creation from webhooks**

Make push and pull-request routes call named lifecycle methods. Return the created scan identity and accepted status. Do not return a fake advisory decision from the webhook response.

**Step 4: Fix diff checkout**

Fetch the exact base and head commits with bounded depth. Calculate `git diff --name-only {base_sha} {head_sha}`. Fail the diff scan if either commit cannot be verified.

**Step 5: Verify and commit**

Commit:

```bash
git add apps/api apps/worker
git commit -m "fix(github): unify scan triggers and pull request scope"
```

### Task 10: Publish advisory GitHub Checks

**Files:**

- Create: `apps/api/app/services/github_checks.py`
- Modify: `apps/api/app/services/github.py`
- Modify: `apps/api/app/services/scan_completion.py`
- Modify: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_github_checks.py`
- Test: `apps/api/tests/test_scan_completion.py`

**Step 1: Write check lifecycle tests**

Require queued, in-progress, completed, and failed check updates. Include scanner-health gaps, finding counts, advisory policy result, and the scan URL. Verify that the check never reports success when evidence is incomplete.

**Step 2: Add an idempotent check publisher**

Store the GitHub check-run ID on the scan. Create it once and update it on later events. Treat GitHub delivery failure as an observable integration failure. Do not roll back committed scan evidence because GitHub is unavailable.

**Step 3: Verify and commit**

Run the GitHub and completion suites. Commit:

```bash
git add apps/api
git commit -m "feat(github): publish advisory scan checks"
```

Gate 3 requires an end-to-end GitHub test installation. Complete installation, push, pull request, base-to-head diff, scan, persistence, and check publication in staging.

## Phase 4: Gate 4, beta operations

### Task 11: Repair access, auditing, and browser API boundaries

**Files:**

- Modify: `apps/api/app/api/v1/routes/scan_schedules.py`
- Modify: `apps/api/app/middleware/audit.py`
- Modify: `apps/api/app/services/audit_logs.py`
- Modify: `apps/api/app/middleware/auth.py`
- Modify: `apps/api/app/core/security.py`
- Modify: `apps/api/app/middleware/redis_rate_limit.py`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/exports/page.tsx`
- Test: `apps/api/tests/test_authorization_regressions.py`
- Test: `apps/api/tests/test_route_integration_authorization.py`
- Create: `apps/api/tests/test_audit_middleware.py`
- Create: `apps/web/lib/api.spec.ts`

**Step 1: Write authorization and audit regressions**

Require 403 for viewer schedule mutations, 401 for inactive users, verified request-local audit actors, project-scoped audit results, and worker-identity audit actors.

Require JWT audience validation in every beta environment. Add proxy-aware rate-limit tests for two client addresses and two organizations. Define explicit behavior when Redis is unavailable instead of silently changing to per-process limits.

**Step 2: Replace process-global audit state**

Use request state populated by verified user or worker authentication. Match the actual `/api/v1` route prefix. Write an audit event after successful mutations with explicit organization and project identity.

**Step 3: Fix browser response handling**

Return `undefined` for 204 responses. Throw a typed contract error when Zod parsing fails. Use `download_url` for completed exports. Keep export navigation hidden until a generator exists.

**Step 4: Verify and commit**

Commit:

```bash
git add apps/api apps/web
git commit -m "fix(access): enforce beta authorization and audit contracts"
```

### Task 12: Create deployable API and dedicated-worker infrastructure

**Files:**

- Create: `apps/api/Dockerfile`
- Create: `apps/worker/Dockerfile`
- Create: `infra/worker/docker-compose.beta.yml`
- Create: `infra/worker/.env.example`
- Create: `scripts/render_worker_config.py`
- Modify: `render.yaml`
- Modify: `Makefile`
- Modify: `apps/api/app/api/v1/routes/health.py`
- Modify: `apps/worker/app/core/alerts.py`
- Modify: `.env.example`
- Create: `docs/runbooks/provision-beta-worker.md`
- Create: `docs/runbooks/rotate-worker-credential.md`
- Create: `docs/runbooks/disable-beta-organization.md`
- Create: `docs/runbooks/dead-letter-recovery.md`
- Create: `docs/runbooks/backup-and-restore.md`
- Create: `docs/runbooks/security-incident-response.md`

**Step 1: Write configuration contract tests**

Add tests that parse the Render Blueprint and worker Compose file. Require valid runtimes, roots, build and start commands, pre-deploy migrations, health checks, pinned images, one scan of concurrency, organization identity, and no database or object-storage account credentials on the worker.

**Step 2: Build the images**

Run the API and worker as non-root users. Pin base images by digest. Add health checks. Keep scanner binaries in the separate pinned scanner image.

**Step 3: Correct the shared deployment**

Keep the API and scheduler in `render.yaml`. Remove the global multi-tenant worker. Set `API_BASE_URL`, migration commands, and actual monorepo build and start configuration. Use `runtime: docker` or valid `runtime: python` syntax.

Make the documented Slack alert variable match the worker implementation. Add dependency-health reporting for the database, queue, storage, and dedicated workers without making the liveness endpoint depend on external services.

**Step 4: Add repeatable worker provisioning**

Generate one organization-specific configuration from an organization ID, service name, queue endpoint, API URL, and secret references. Do not write secret values to generated files or logs.

**Step 5: Execute every runbook in staging**

Record timestamps, operator, result, and evidence for provisioning, rotation, replacement, kill switch, dead-letter recovery, backup, restore, and incident response.

**Step 6: Verify and commit**

Commit:

```bash
git add apps/api apps/worker infra scripts/render_worker_config.py render.yaml Makefile .env.example docs/runbooks
git commit -m "ops: add secure private beta deployment"
```

### Task 13: Add production-backed integration and gate tests

**Files:**

- Modify: `docker-compose.yml`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/integration/test_private_beta_evidence.py`
- Create: `tests/integration/test_worker_isolation.py`
- Create: `tests/integration/test_queue_recovery.py`
- Create: `tests/e2e/test_github_beta_workflow.py`
- Create: `scripts/verify_private_beta_gate.py`
- Modify: `Makefile`

**Step 1: Add real backing services**

Run API tests against PostgreSQL 16. Run queue tests against Redis 7 Streams. Run artifact tests against MinIO. Apply Alembic migrations before tests.

**Step 2: Add failure injection**

Automate API 500, transaction rollback, worker kill, Redis interruption, scanner timeout, artifact upload failure, duplicate delivery, cancellation race, wrong-organization worker, and canary-secret scenarios.

**Step 3: Add browser and GitHub simulation**

Use Playwright for onboarding, scan history, scanner health, finding triage, and advisory-check status. Stub GitHub only in CI. Keep one staging test against a real GitHub App installation.

**Step 4: Add one gate command**

Implement:

```bash
make private-beta-gate
```

The command must fail on any lint, type, unit, integration, migration, build, audit, isolation, or canary-secret failure.

**Step 5: Verify and commit**

Run `make private-beta-gate`. Commit:

```bash
git add docker-compose.yml .github/workflows/ci.yml tests scripts/verify_private_beta_gate.py Makefile
git commit -m "test: enforce secure private beta gates"
```

### Task 14: Onboard the three-organization cohort

**Files:**

- Create: `docs/runbooks/onboard-design-partner.md`
- Create: `docs/runbooks/private-beta-expansion-gate.md`
- Create: `docs/templates/private-beta-acceptance-record.md`
- Modify: `spec/SECURE_PRIVATE_BETA.md` only if an approved requirement changes

**Step 1: Prepare an acceptance record per organization**

Record GitHub installation, approved repositories, worker identity, worker deployment, queue namespace, artifact prefix, retention check, first scan, failure drills, backup and restore drill, operator, and customer sign-off.

**Step 2: Onboard one organization at a time**

Do not provision the next partner until the current partner completes the first-scan and isolation checks.

**Step 3: Hold the expansion gate**

After three partners complete two stable weeks, review every measure in `spec/SECURE_PRIVATE_BETA.md`. Add organizations four and five only when every gate passes and no evidence-integrity or isolation incident remains open.

**Step 4: Commit the reusable records**

Do not commit customer names, repository names, credentials, or incident data. Commit only sanitized templates and runbooks.

```bash
git add docs/runbooks docs/templates
git commit -m "docs: add private beta operating playbook"
```

## Final verification

Run:

```bash
make private-beta-gate
git status --short
```

Expected:

- The gate exits 0.
- The worktree contains only intentional documentation or release-record changes.
- A clean staging deployment passes all four quality gates.
- Three organization-specific workers have distinct identities, queue namespaces, and artifact prefixes.

## Deferred work

Do not include KEV, EPSS, Jira, merge blocking, automated fixes, SAML, SCIM, GitLab, Bitbucket, AI investigation, or public pricing in these implementation tasks. Start a separate plan after the private beta expansion gate.
