# R12 Recovery Drill Runbook

Status: local-disposable drills executed (results below are real captured
output); staging execution is OPEN and gated on a real deployment.

Scope: evidence-prep for readiness plan R12 ("Prove deployment and
operational recovery", docs/plans/2026-09-13-evidence-first-readiness-plan.md).
These drills rehearse, on disposable local infrastructure, the parts of R12
that do not require a real environment: migration up/down/up, completion
receipt rollback semantics (R04/D6), and queue XAUTOCLAIM recovery. No app
code, schema, or CI changes are included.

## Prerequisites

- Repository checkout at or after the drill commit; run from
  `scanforge-security-platform/` (repo root).
- `uv` on PATH (scripts create `apps/api/.venv` and `apps/worker/.venv` on
  first use; `pgserver` and `fakeredis` are added to those venvs only if
  missing).
- Linux with GNU `date` (timings use `%s%N`).
- No services required up front: PostgreSQL comes from the disposable
  `pgserver` cluster (`/tmp/scanforge-r12-*-pg16`), Redis is probed at
  `127.0.0.1:6379` (override `R12_REDIS_HOST`/`R12_REDIS_PORT`); fallbacks are
  a spawned `redis-server` on port 6390, then fakeredis (labeled).
- `DATABASE_URL` may be set to anything or unset: migration drill sets it to
  the disposable URI; rollback drill only needs it to exist for settings
  import and defaults to an in-memory SQLite URL.
- Approval note (plan R12): drills here are all disposable-fixture, no
  staging target is touched. Operator approval is still required before any
  staging deployment or destructive drill.

## Drill 1: migrations (up -> down -> up on empty disposable PG)

Command:

```bash
./scripts/rehearse_migrations.sh
```

What it does: creates a throwaway PostgreSQL 16 cluster with `pgserver`
(documented in docs/development-setup.md, "Disposable PostgreSQL for test
evidence"), points `DATABASE_URL` at it, and times `alembic upgrade head`,
`alembic downgrade base`, and `alembic upgrade head` again. Exits non-zero if
any step fails; removes the cluster directory afterwards
(`R12_KEEP_PGDATA=1` to keep for inspection).

Expected output shape:

```
[rehearse_migrations] disposable PostgreSQL ready at /tmp/scanforge-r12-migrations-pg16
[rehearse_migrations] STEP alembic upgrade head     OK    <ms> ms
[rehearse_migrations] STEP alembic downgrade base   OK    <ms> ms
[rehearse_migrations] STEP alembic upgrade head (2) OK    <ms> ms
[rehearse_migrations] alembic head: <revision>
[rehearse_migrations] RESULT: PASS (upgrade head -> downgrade base -> upgrade head, all steps green)
```

Pass criteria: all three steps report `OK`; exit code 0.

Actual local-disposable result: see "Captured local outputs" below.

## Drill 2: completion rollback / receipt semantics (SQLite + disposable PG)

Command:

```bash
./scripts/rehearse_rollback.sh
```

What it does: drives `ScanCompletionService.complete` through the documented
R04 receipt semantics (spec/2026-09-13-scan-evidence-decisions.md D6) on
SQLite and, in a second phase, on an empty disposable pgserver PostgreSQL:

1. first completion writes exactly one server-owned receipt,
2. identical replay returns the stored receipt (`replayed=True`) and does not
   write a second receipt row,
3. conflicting replay of the same completion identity raises
   `CompletionPayloadConflict` (conflict family surfaced as HTTP 409),
4. stale-identity replay raises `CompletionSuperseded` (HTTP 409 family),
5. receipt stays durable and single-row after the conflict attempts.

Pass criteria: both phases print the five check lines and exit 0.

Actual local-disposable result: see "Captured local outputs" below.

## Drill 3: queue recovery (consumer killed mid-claim, XAUTOCLAIM reclaim)

Command:

```bash
./scripts/rehearse_queue_recovery.sh
```

What it does: starts a labeled Redis backend (local Redis if reachable, else
spawned `redis-server`, else fakeredis), fronts it with an Upstash-REST
protocol shim so the production `QueueClient` runs unchanged, enqueues 5
synthetic `QueueJob` messages, starts a real consumer process, SIGKILLs it
right after it claims one delivery (before ack), then runs a recovery
consumer and verifies the orphaned pending entry is reclaimed through the
production XAUTOCLAIM path with zero message loss. Prints claim latency,
recovery latency, and end-to-end drain time. The drill overrides only
`visibility_timeout_ms` (300 ms instead of the 30-minute default) on the
drill client subclass; app code is untouched.

Expected output shape:

```
[rehearse_queue_recovery] backend: <labeled backend>
[rehearse_queue_recovery] enqueued 5 synthetic messages in <ms> ms
[rehearse_queue_recovery] victim consumer claimed r12-drill-scan-0 (entry <id>) in <ms> ms
[rehearse_queue_recovery] victim consumer SIGKILLed mid-claim (pending entry <id> orphaned)
[rehearse_queue_recovery] delivered map: {...}
[rehearse_queue_recovery] XAUTOCLAIM recovered orphaned message r12-drill-scan-0 in <ms> ms
[rehearse_queue_recovery] end-to-end (first recovery poll -> last ack): <ms> ms; pending=0; stream_len=0; dlq=0
[rehearse_queue_recovery] RESULT: PASS (0 lost, 0 stranded pending, XAUTOCLAIM reclaim proven, latency above)
```

Pass criteria: delivered map has exactly 5 distinct job ids, the killed
message is the only duplicate (delivered exactly twice: once by the victim,
once by recovery), `pending=0`, `stream_len=0`, `dlq=0`, exit code 0.

Actual local-disposable result: see "Captured local outputs" below.

## Captured local outputs (local-disposable evidence)

Environment: Linux worktree `/tmp/scanforge-r12-prep` at the drill commit;
api/worker venvs on CPython 3.12 (uv); PostgreSQL via pgserver disposable
clusters under /tmp; Redis via local `127.0.0.1:6379`. All outputs below are
real captured runs of the three scripts, exit code 0 each.

### Drill 1 output (local-disposable pgserver PostgreSQL)

```
[rehearse_migrations] disposable PostgreSQL ready at /tmp/scanforge-r12-migrations-pg16 (socket port 5432)
[rehearse_migrations] STEP alembic upgrade head     OK      1869 ms
[rehearse_migrations] STEP alembic downgrade base   OK      1279 ms
[rehearse_migrations] STEP alembic upgrade head (2) OK      1714 ms
[rehearse_migrations] alembic head: 0021_scan_execution_lease
[rehearse_migrations] RESULT: PASS (upgrade head -> downgrade base -> upgrade head, all steps green)
EXIT=0
```

### Drill 2 output (local-disposable SQLite + pgserver PostgreSQL)

```
[rehearse_rollback] phase 1: SQLite backend
[r12_rollback_drill] sqlite: first completion -> receipt (replayed=False)
[r12_rollback_drill] sqlite: identical replay -> stored receipt returned, still 1 receipt row
[r12_rollback_drill] sqlite: conflicting replay -> CompletionPayloadConflict (HTTP 409 family)
[r12_rollback_drill] sqlite: stale-identity replay -> CompletionSuperseded (HTTP 409 family)
[r12_rollback_drill] sqlite: receipt durable after conflicts (terminal_status=completed, 1 row)
[r12_rollback_drill] sqlite: drill wall time 136 ms
[rehearse_rollback] phase 2: disposable PostgreSQL backend (pgserver)
[r12_rollback_drill] postgres: first completion -> receipt (replayed=False)
[r12_rollback_drill] postgres: identical replay -> stored receipt returned, still 1 receipt row
[r12_rollback_drill] postgres: conflicting replay -> CompletionPayloadConflict (HTTP 409 family)
[r12_rollback_drill] postgres: stale-identity replay -> CompletionSuperseded (HTTP 409 family)
[r12_rollback_drill] postgres: receipt durable after conflicts (terminal_status=completed, 1 row)
[r12_rollback_drill] postgres: drill wall time 323 ms
[rehearse_rollback] RESULT: PASS (receipt replay + conflict 409 semantics on SQLite and disposable PG)
EXIT=0
```

### Drill 3 output (local Redis 127.0.0.1:6379, real backend — NOT a fallback)

```
[r12_queue_recovery] backend: local-redis 127.0.0.1:6379
[r12_queue_recovery] upstash-REST shim at 127.0.0.1:42435 (drill-only harness)
[r12_queue_recovery] enqueued 5 synthetic messages in 2 ms
[r12_queue_recovery] victim consumer claimed r12-drill-scan-0 (entry 1789347189312-0) in 559 ms
[r12_queue_recovery] victim consumer SIGKILLed mid-claim (pending entry 1789347189312-0 orphaned)
[r12_queue_recovery] delivered map: {'r12-drill-scan-1': 1, 'r12-drill-scan-0': 2, 'r12-drill-scan-2': 1, 'r12-drill-scan-3': 1, 'r12-drill-scan-4': 1}
[r12_queue_recovery] XAUTOCLAIM recovered orphaned message r12-drill-scan-0 in 471 ms
[r12_queue_recovery] end-to-end (first recovery poll -> last ack): 1429 ms; pending=0; stream_len=0; dlq=0
[r12_queue_recovery] orphaned entry 1789347189312-0 redelivered exactly once after XAUTOCLAIM
[r12_queue_recovery] RESULT: PASS (0 lost, 0 stranded pending, XAUTOCLAIM reclaim proven, latency above)
EXIT=0
```

Interpretation notes (local-disposable evidence only):

- Migration numbers are from an empty disposable PG16 cluster on a laptop
  class machine; they show correct up/down/up behavior, not staging
  performance.
- Queue recovery was exercised against a local Redis behind a drill-only
  Upstash-REST protocol shim so the production `QueueClient` code path
  (including XAUTOCLAIM) ran unmodified. It does not measure Upstash
  production latency or rate-limit behavior.
- Rollback drill runs the service layer directly; the HTTP 409 mapping is the
  documented conflict-family contract, not a live HTTP round trip.


## OPEN: what only a real staging deploy can prove

Nothing below is claimable from local drills. Each item stays OPEN until
executed against staging and recorded with sanitized evidence:

- Clean deploy of `render.yaml`: service provisioning from the blueprint
  (API, scheduler, dedicated worker), first-deploy success, and absence of
  broad credentials in the rendered services (ADR-009 boundary).
- Host capacity: real p95 latency and peak process RSS under the declared
  beta load fixture on the actual worker host class (plan G1: no v1
  enablement before recorded host memory/concurrency evidence).
- Beta concurrency: the declared fixture arrival rate with at least 95% of
  scans starting within five minutes and fault recovery within ten minutes.
- Slack/alert paths: delivery of recovery and DLQ alerts to the real
  notification channels, with detection-time evidence.
- Upstash production endpoints: queue behavior against the real Upstash REST
  service (latency, 429/rate-limit handling, group semantics) instead of the
  local shim; includes DLQ and retry-zset promotion on production Redis.
- Render environment variable/secret wiring, migration execution on the real
  managed PostgreSQL (empty-database provision plus upgraded sanitized
  staging copy), and backup/restore behavior of the managed stores.

Runbook for staging execution: run the three drills against staging
endpoints, then record the staging numbers, failure-injection time, detection
time, recovery time, and data-integrity checks in the R12 evidence location.
