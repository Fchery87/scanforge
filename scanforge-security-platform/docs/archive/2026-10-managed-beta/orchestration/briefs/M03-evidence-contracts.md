# M03 — Authoritative versioned execution and evidence contracts

Depends on: M00; serialized after M02 in the API track. Status: brief ready; spawn gated on the pilot contract and M02 completion.

## GOAL

One versioned contract authority for scan execution and evidence, owned by the API, that defines required and forbidden fields, coverage and outcome semantics, provenance and revisions, and from which worker DTOs are derived without a second authority.

## SCOPE

Work in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/scanforge-security-platform` on branch `managed-beta/integration` at whatever head M02 landed.

- Schemas: `apps/api/app/schemas/scans.py`, `scan_completion.py`, `canonical_findings.py` (adjust names to what exists).
- Models: `apps/api/app/db/models/scan.py`, `repository.py`, `finding.py`, `artifact.py`; `apps/api/app/db/enums.py`.
- Contracts: both `app/contracts/queue.py` modules (api and worker). Keep them textually identical or generated from one source; the current duplication is manual.
- Create `apps/api/app/services/evidence_contract.py` as the single validation authority; create matching worker DTOs without duplicating validation logic.
- Alembic: one additive revision (you are the single migration writer; inspect current heads first). Additive records only: identities, obligations, provenance, revisions, receipts. Domain-specific types, not generic JSON authority flags.
- Tests: extend `test_canonical_finding_candidates.py` and both queue-contract suites; create `test_evidence_contract.py`.

## CONTEXT

- Plan authority: task M03 in the managed-beta plan; ADR-017 (`ADR-017-authoritative-evidence-and-optional-ai.md`) and ADR-014 (`ADR-014-finding-identity-and-provenance.md`) in the shared tree docs/adr/, read-only.
- Convention map: `orchestrate/managed-beta/reports/exp-api.md` (contract duplication detail, model inventory, no-conftest test style).
- Exact canonical sorting details are engineering specifications constrained by the plan's Q42 reference, not product choices; do not invent new product semantics.
- Never commit credential-looking literals; never retype SHAs (use `git rev-parse HEAD`). The fixture script `scripts/dev_fixtures.sh print-env` exports the database URL.

## ACCEPTANCE

1. Fixture matrix in `test_evidence_contract.py`: full, partial and unknown coverage; explicit scanner outcomes (success, failure, timeout, unavailable); immutable revision and provenance fields; cleanup-pending state; superseded unstarted work.
2. Contract defines required and forbidden fields per version; negotiation rejects unsupported versions with a documented error; duplicate and unknown scanner entries reject.
3. Deterministic collection identities and server-owned derived values (counts, completeness, lifecycle eligibility) are computed server-side; worker-supplied values for those fields are ignored or rejected, proven by test.
4. Artifact availability is modeled separately from scanner coverage.
5. Bounded ingress: candidate limits enforced in the contract layer, with no claim of G1 capacity approval.
6. OpenAPI regenerated (`cd apps/api && .venv/bin/python scripts/emit_openapi.py`) and client types regenerated (`cd apps/web && npm run gen:types`); both diffs reviewed and included.
7. Focused contract suites green; one schema/contract commit plus separate commits for the revision and any model changes, only enumerated paths, SHAs reported.

## VERIFY

- `cd apps/api && .venv/bin/python -m pytest tests/test_evidence_contract.py tests/test_canonical_finding_candidates.py tests/test_queue_contract.py -q` plus the worker-side contract suite run from `apps/worker` with its venv.
- `alembic history` head count still one; `alembic upgrade head` against the M00 fixture database at 5433 succeeds from base.
- `git show --stat` per commit.

## TIMEBOX

2.5 hours. FORBIDDEN: parallel authorities for validation, generic JSON blobs carrying authority, second migration writer, edits outside enumerated paths, claims about capacity approval.

## REPORT

Status, branch, per-commit SHAs, contract version semantics summary, suite outputs, OpenAPI/client regen evidence, deviations, follow-ups.
