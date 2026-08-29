# Gate 1 Completion TODO

Source: `docs/plans/2026-08-19-secure-private-beta-implementation-plan.md`, Phase 1.

## Task 2 — Worker identity and scheduler authority

- [x] Add organization-scoped, hashed worker identities and capability checks.
- [x] Reject cross-organization worker access.
- [x] Authenticate the shared scheduler separately from customer workers.
- [x] Test scheduler authentication failures and prove worker credentials cannot run all organizations' schedules.
- [x] Verify migrations `0017` and `0018` upgrade/downgrade against disposable PostgreSQL.

## Task 3 — Durable organization Redis Streams

- [x] Use organization-specific stream and dead-letter keys.
- [x] Use consumer groups, pending entries, `XAUTOCLAIM`, acknowledgment, and deletion.
- [x] Use scan IDs as enqueue idempotency keys.
- [x] Add a real Redis recovery integration test: terminate after delivery, reclaim with a second consumer, preserve scan ID.
- [x] Ensure DLQ transfer occurs before acknowledgment/deletion of the original entry.

## Task 4 — Atomic, idempotent completion

- [x] Add a single completion endpoint and reject completion through progress updates.
- [x] Commit scanner runs, findings, occurrences, summary, lifecycle evaluation, and final status in one transaction.
- [x] Add occurrence idempotency constraint and fingerprint.
- [x] Add focused completion tests for rollback, duplicate delivery, canceled completion, scanner health, and lifecycle ordering.
- [x] Add worker tests for HTTP 500 and timeout: no queue acknowledgment and job remains recoverable.
- [x] Correct any atomicity/idempotency defects exposed by those tests.

## Task 5 — Terminal cancellation

- [x] Reject progress and completion writes after cancellation.
- [x] Read authoritative scan state before clone, scanner execution, artifact upload, and completion.
- [x] Acknowledge canceled jobs without publishing evidence.
- [x] Add API and worker cancellation race tests.

## Gate 1 verification

- [x] API and worker focused Phase 1 tests pass.
- [x] Full API suite passes and terminates; PostgreSQL migration upgrade/downgrade is verified.
- [x] `make lint` passes.
- [x] `make test` passes (API: 136, worker: 54, web: 21 files / 78 tests).
- [x] Web Vitest suite passes: 21 files, 78 tests.
- [x] Web dependency audit passes with 0 high/critical vulnerabilities.
- [x] Web ESLint and production build pass.
- [x] Gate 1 is green.

## Repository metadata

- [x] The valid Git repository is the parent directory (`scanforge`); project changes are tracked at `scanforge-security-platform/...`.
- [ ] Create the required task commits from the parent repository root.
