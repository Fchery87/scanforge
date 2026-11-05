# M06 — Repository authority, exact revisions, branch continuity

Track: api. Depends on: M02 + M03. Status: brief ready; spawn gated on M03.

## GOAL

Repository bindings carry verified provider authority, scans pin exact immutable revisions, and branch continuity is proven by provider-backed ancestry so absence can never close a finding across a broken lineage.

## SCOPE

Work in the api-track worktree on a fresh branch off the integration head at spawn time.

- Modify: `apps/api/app/services/github.py`, `repositories.py`, `scans.py`, repository/ref models, `apps/api/app/api/v1/routes/github.py`, `repositories.py`, `internal.py`; `apps/worker/app/services/scan_pipeline/context.py`, `execution.py`.
- Create: `apps/api/app/services/repository_refs.py`, `apps/api/tests/test_repository_ref_identity.py`.
- Tests: extend `test_execution_context_identity.py`.

## CONTEXT

- Plan authority: task M06 in the managed-beta plan; ADR-012 (`ADR-012-repository-authority-and-ordered-evidence.md`) and ADR-016 in the shared tree docs/adr/, read-only.
- Convention map: `orchestrate/managed-beta/reports/exp-api.md`. Repositories carry provider/full_name/external_repo_id today; scans carry commit_sha/base_sha/attempt_id.
- Preserve M01's capability guards; M02/M03's landed shapes are your base.

## ACCEPTANCE

1. Fixture matrix: foreign installation, unverified binding, rename, transfer, queued branch movement, inaccessible SHA, force-push, branch recreation. Each proves the intended authority denial or generation behavior.
2. Connecting user's installation access is verified server-side; an installation binds to one organization and a repository binds to one project via immutable provider IDs before any uniqueness reservation.
3. Exact revision/full-ref/generation/coverage policy resolves BEFORE dispatch; checkout verifies the exact SHA and never substitutes the branch tip; full ref names and generation evidence persist.
4. Provider-backed ancestry receipts: unknown or non-descendant continuity starts a new generation and never grants absence credit; default-branch and manually requested scopes stay explicit.
5. Real local Git fixture (non-production) proves checkout/verify behavior; provider interactions are contract-tested; unchanged histories are asserted unchanged.
6. Focused suites green; invariant-per-commit, enumerated paths only, SHAs via rev-parse.

## VERIFY

- `cd apps/api && .venv/bin/python -m pytest tests/test_repository_ref_identity.py tests/test_execution_context_identity.py -q`.
- `git show --stat` per commit; the Git-fixture evidence lines pasted.

## TIMEBOX

3 hours. FORBIDDEN: trusting stored clone URLs over verified bindings, branch-tip substitution, absence credit across generations, credential literals, edits outside enumerated paths, second migration writer.

## REPORT

Status, branch, per-commit SHAs, fixture-matrix outcomes, Git-fixture evidence, suite outputs, deviations, follow-ups.
