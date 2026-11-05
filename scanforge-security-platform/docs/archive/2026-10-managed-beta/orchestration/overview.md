# Managed beta program overview

Plan: `scanforge-security-platform/docs/plans/2026-10-16-managed-beta-implementation-plan.md` (untracked in shared tree, preserved there by name only).

Baseline: `main` at `6062170b9307553430490aa364d778f503bfde2`.

Integration branch: `managed-beta/integration` in worktree `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta`. Local only. No merges authorized by the plan.

## Done predicate

All 16 tasks M00–M15 delivered as commits on the integration branch, each task's plan checklist carried by evidence, every unit ledger-verified at `unit-test-verified` or better, real-service checks either passed or explicitly `verifier-blocked` with the missing runtime named, and operator-only gates parked in `gates.md`. M15 envelope approval and staged release stay with the operator.

## Dependency graph (from the plan tracker)

- M00 first.
- M01, M02, M03 after M00 (API track, serialized edits).
- M04 after M03 (worker track). M05 after M04.
- M06 after M02+M03. M07 after M03+M06. M08 after M02+M04+M07. M09 after M02+M05+M08. M10 after M06+M09. M11 after M02+M06+M07+M08.
- M12 after M01+M02+M09+M10+M11 (may develop against accepted contracts earlier; integration acceptance waits for real services).
- M13 after M02+M08+M09. M14 after M03+M08+M09+M10+M13. M15 after M04–M14.

## Tracks

| Track | Tasks | Writes |
| --- | --- | --- |
| intake | M00 | infra/testing, scripts, docs/receipts |
| api | M01, M02, M03, M06, M07, M08, M09, M10, M11, M13, M14 | apps/api, serialized, one Alembic writer |
| worker | M04, M05 | apps/worker, render.yaml, deployment templates |
| web | M12 | apps/web + browser suite |
| ops | M15 | scripts, CI, monitoring, dossier |

Worker and web tracks run parallel to api when their deps land; scopes are disjoint by path.

## Environment

PostgreSQL 16 native binaries (`/usr/lib/postgresql/16/bin`), disposable cluster on 5433. Native redis-server on 6399. MinIO single binary on 9002 (download into `.fixtures/bin/`). All seven scanners installed natively. Docker absent, no sudo (gate `docker-runtime`).

## Gates

- `docker-runtime`: open. Default: native pinned binaries; container-fidelity checks recorded verifier-blocked.
- `github-app`: open. Default: fixtures only; live App delivery unverified.
- `landing`: open. Default: integration branch stays local; operator decides push and landing.

## Authority doc locations

ADR-010 through ADR-017 exist only in the shared tree at `scanforge/scanforge-security-platform/docs/adr/`. The worktree checkout at 6062170 carries ADR-001 through 009 only. Workers read ADRs from the shared path, read-only, and never write there.

## Ledger keying (no PRs exist; landing is local)

Ledger `pr` field carries the unit sequence: 1=M00, 2=M01, 3=M02, 4=M03, 5=M04, 6=M05, then task number - 5 for M06+ (7=M12? no: sequence continues 6=M06 ... ). Mapping is appended here as units land. Landed: pr1 reserved for M00 (awaiting operator commit), pr1 used for M01 = e5d8de7.

Correction: the sequence counter is chronological, not per-task. Each ledger row's SHA is the source of truth; `orch ledger check <n> <sha>` verifies.
