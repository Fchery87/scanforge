# Redirection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the existing scanner platform into a trustworthy baseline for developer-first security review, then run scanner-backed PR review in private shadow mode on real repositories, starting with ScanForge itself.

**Architecture:** Keep the current shared control plane (Next.js / FastAPI / PostgreSQL / Redis Streams) and dedicated per-organization scanner hosts. The API stays the only authority for identity, authorization, lifecycle, coverage and publication; workers and (later) AI submit evidence. Phase 1 makes "fixed" mean fixed (analyzer comparability, stable identity, one dependency engine, capability-scoped lifecycle). Phase 2 adds PR analysis that records results privately and reconciles them across commits before anything is published.

**Tech stack:** FastAPI/Pydantic, SQLAlchemy/Alembic/PostgreSQL, Redis Streams, Python worker with digest-pinned scanner containers (Trivy, Gitleaks, OSV-Scanner, Semgrep, Syft, Checkov, Grype), Next.js/TypeScript, GitHub App, pytest.

**Authority:** [Product charter](../PRODUCT_CHARTER.md), [ADR-018](../adr/ADR-018-developer-first-security-review-direction.md), ADR-010–017 and [CONTEXT.md](../../CONTEXT.md). This plan replaces the [October managed-beta plan](../archive/2026-10-managed-beta/2026-10-16-managed-beta-implementation-plan.md) for execution order. It does not authorize deployment, customer scans, GitHub publication, infrastructure purchases, dependency installation, destructive migrations, merges or pushes.

**Baseline:** `main` at `f5a47dd` (2026-11-04). Recheck with `git rev-parse main` before each task.

---

## Execution rules

1. **One tracker, updated in the same commit as the work.** A row becomes `Done` only when it cites the commit SHA (from `git rev-parse`) and the exact test command that passed. Never retype SHAs or counts from prose.
2. **Regression first.** Write the failing test, run it, record the failure, then implement the minimum change.
3. **Commit messages state scope honestly.** No "complete"/"finish" titles unless every acceptance check in that task passed.
4. **A missing service is "not run", never "pass".** PostgreSQL concurrency, real scanner containers and GitHub App delivery require the real thing; record `verifier-blocked: <missing dependency>` otherwise.
5. **Capabilities stay disabled** in [beta_capabilities.py](../../apps/api/app/core/beta_capabilities.py) until their task's gate passes. Shadow execution never publishes to GitHub.
6. **Additive migrations only**; inspect `alembic heads` first; one migration writer at a time. Never recalculate historical identities silently.
7. **Stage only enumerated paths.** Never stage `.env`, evidence logs or unrelated user changes.
8. Regenerate OpenAPI and web types after schema/route changes: `make` targets in the [Makefile](../../Makefile).

Working directories: API commands run from `apps/api`, worker commands from `apps/worker`, using each app's existing `.venv`. The Git root is the parent `scanforge/` directory.

## Production-readiness follow-up (2026-11-07)

The user authorized completing the older hardening backlog after spec #32 merged
at `93d967e`. Work is collected on `integration/production-readiness` in
[PR #60](https://github.com/Fchery87/scanforge/pull/60). Existing implementations
are verified rather than replaced. Disabled capabilities remain disabled.

| Issues | Status | Evidence |
| --- | --- | --- |
| #56 | Closed | Merged API dispatch regression passed; clean `npm ci --ignore-scripts && npm audit --audit-level=high` exited 0 (remaining advisories low/moderate only). |
| #4 | Implemented | `ba42175`, `bd17a6e`: root CI gates protected by executable tests; CI `api`, `worker`, `web`, `required`, and `changes` checks passed on the integration branch. SBOM remains conditionally skipped when its tool is unavailable. |
| #6 | Implemented | `45ce08b`: default-off coverage and unconfigured provider skip; focused AI stage suite passed and the integrated worker suite passed (239 passed, 2 skipped). |
| #9, #13 | Implemented | `a6d52ee`, `6cbf005`: trusted-proxy identity for both limiter paths, spoof-resistant chain traversal, readiness/liveness coverage; integrated API focused middleware suite passed (32 passed). |
| #2, #3, #5, #7, #8, #10, #11, #12, #14, #15, #16, #57, #58 | Implemented on `integration/production-readiness` | `b808cdc` is the current tip. Full integrated API suite: 601 passed, 23 skipped. Full worker suite: 239 passed, 2 skipped. Web Node suite: 80 passed; Vitest: 28 passed; lint and production build passed. Queue acceptance suite: 22 passed. |
| #1 | Ready for maintainer review | All requested code and verification work is integrated. Live GitHub/browser/provider workflows, real scanners, real Redis, deployment, and production database operation remain unverified. |

No production migrations, live customer scans, provider credentials, or feature
enablement are authorized by these checks. PostgreSQL rehearsal uses a newly
created disposable local cluster. Browser/live-provider and real-scanner evidence
must be reported separately rather than inferred from unit tests.

## Tracker

Spec: [issue #32](https://github.com/Fchery87/scanforge/issues/32). Each slice is a sub-issue labelled `ready-for-agent`. The issues' native "blocked by" links are the authoritative dependency graph; the "Depends on" column below summarizes them. Close an issue only when its tracker row here is `Done` with SHA and test command.

| ID | Task | Issues | Depends on | Pilot-blocking | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Documentation cleanup, ADR-018, this plan | — | — | yes | Done | Branch `docs/product-redirection`; [cleanup report](../reviews/2026-11-04-cleanup-report.md) |
| P1.1 | Absence credit requires comparable analyzers (G1) | #33 | — | yes | Done (branch `fix/33-comparable-analysis-absence`, `ea4c26b` + fix commit) | Focused suites (Step 11): 57 passed, 1 skipped (PostgreSQL case, `R05_POSTGRES_URL` unset), 1 failed in isolation; the failure predates this work (#57). Full suite: 271 passed, 8 skipped (baseline 257 passed, 8 skipped). `ruff check app` clean. Step 12: the completion path commits not-credited/untransitioned absence metadata (`scan_completion.py` commits after the `commit=False` call); the `commit=True` path skips its commit when nothing transitions, reachable only via the uncalled `mark_not_observed_for_completed_scan` wrapper (latent, not fixed) |
| P1.2 | Clone isolation and exact-SHA requirement (G4, G5) | #34 | — | yes | Done (local git fixtures only) | #34: `0232bdf` (git isolation, exact-SHA requirement); `91e617f` (exact head SHA resolved at manual and scheduled scan creation). Worker clone-isolation and fork-config tests in the worker suite |
| P1.3 | Verify carried-forward M07/M08 acceptance | #35 (M07), #36 (M08 fencing) | — | yes | Done (PostgreSQL run reported by the implementer, not re-run in review) | #35: `742d7e7` (serialized ref transitions, duplicate-trigger rollback isolation; M07 table above). #36: `6337a70` (terminal-scan write fencing, context-refetch adoption). Review C10: the worker's refetch sends the identity it holds (`test_scan_orchestrator.py`) |
| P1.4 | Primary dependency engine evaluation | #37 | — | yes | Done-provisional | #37: `7bf9e35` (default full scan runs Trivy + Syft), `80d7d10`, `48be198` ([ADR-019](../adr/ADR-019-primary-dependency-engine.md) provisional, corpus and harness). The engine evaluation was NOT RUN, so the acceptance 'evaluation document with raw counts' is unmet; ADR-019 is not accepted by the maintainer |
| P1.5 | Fingerprint policy `fp.v3` (G2, G3) | #38 (source/secret), #39 (dependencies), #40 (successor links + timeline) | #33; #39 also #37 | yes | Done | #38: `eb67f4a` (fp.v3 for Semgrep, Checkov, Gitleaks); #39: `fd6c745` (dependency identity); #40: `2323fae` (exact successor links, timeline). Existing fp.v2 findings are preserved, not recalculated |
| P1.5b | Dependency absence requires inventory evidence | #42 | #39, #41 | yes | Done | #42: `855df50` (dependency absence requires same-scan Syft inventory evidence) |
| P1.6 | Capability-scoped absence (G6) | #41 | #33, #37 | yes | Done | #41: `d1400b2` (capability-scoped absence). Review S3: API and worker capability maps pinned by `apps/api/tests/test_capability_registry_parity.py` |
| P1.7 | Artifact finalization and server-derived completion (carried M09) | #43 (artifacts), #44 (canonical completion) | #36 | yes | Done (no real object store exercised) | #43: `44044db` (verified immutable artifact finalization); #44: `0e39d35`, `58ba337` (counts and audit derived from validated canonical evidence) |
| P1.8 | Coverage assessment record | #45 | #41 | yes | Done | #45: `7b3b131` (per-capability coverage assessment on scan detail) |
| P2.1 | PR revision identity and baseline comparison | #46 (shadow runs), #47 (new/existing/unknown) | #34, #35; #47 also #38, #39, #41, #45 | yes | Done (migrations 0025-0029 never run) | #46: `ee7c6e4`, `bbb118a`, `1d14ad5` (private PR shadow runs with recorded base/head/merge-base; fork heads untrusted, no credentials); #47: `6d8568e` (new / existing / unknown against a comparable merge-base baseline). Review notes C1-C5 are in [SYSTEM_OVERVIEW](../SYSTEM_OVERVIEW.md) |
| P2.2 | Shadow PR analysis on ScanForge's own repository | #48 (debounce/supersede); enabling on ScanForge is an operator step | #46 | yes | Partly done | #48: `af766fa` (debounce and supersede obsolete shadow runs). Not done: enabling shadow on ScanForge's own repository is an operator step and was not performed |
| P2.3 | Cross-commit reconciliation of shadow results | #49 | #47, #48 | yes | Done | #49: `8972a77` (candidate reconciliation across pushes; out-of-order head guard; review C3/C4 hardening) |
| P2.4 | One framework review pack (FastAPI first) | #52 | #46 | yes | Done | #52: `a77edd6`, `a70f7fe` (FastAPI review pack `fastapi.v1`; pack id, version and rules digest recorded in the run summary and Semgrep run metadata). Detection-gated, not comprehensive |
| P2.5 | GitHub ingress reconciliation (carried M11) | #53 (lifecycle), #54 (missed events) | #35; #54 also #53 | yes | Done (live GitHub never exercised) | #53: `511b765` (installation and repository lifecycle); #54: `82ac60f` (missed-event reconciliation to the current head with persisted receipts, no fabricated intermediate observations). Lifecycle handlers verified idempotent (review C8) |
| P2.6 | Shadow results view and evaluation corpus | #50 (view + labels), #51 (corpus) | #49 | yes | Done | #50: `51a59da` (shadow results view and reviewer labels); #51: `7ba9549` (replay evaluation corpus, split, retention sweep, tenant cascade). Retention default is a maintainer decision |
| P2.7 | Pilot gate: two design-partner repositories in shadow | Operator/human (no agent issue) | P2.1–P2.6 | yes | Not started | |
| P3 | Bounded contextual reviewer, publication, feedback | — | P2.7 | no | Deferred | Expand into its own plan when P2.7 passes |
| P4 | Reachability, fix suggestions, exports, more frameworks | — | P3 | no | Deferred | |

**Verification note (integration tip `b808cdc`).** The integrated suites were run with an in-memory SQLite database for the API and local package environments: API `DATABASE_URL=sqlite+aiosqlite:///:memory: PYTHONPATH="$PWD/apps/api" uv run --project apps/api --extra dev pytest apps/api -q` produced 601 passed and 23 skipped; worker `PYTHONPATH="$PWD/apps/worker" uv run --project apps/worker --extra dev pytest apps/worker -q` produced 239 passed and 2 skipped. Web `npm run test:node` produced 80 passed, Vitest produced 28 passed, `npm run lint` passed, and `npm run build` passed. The queue recovery suite produced 22 passed. These results do not prove live PostgreSQL, Redis, Docker/scanner images, real scanners, live GitHub or GitHub App delivery, browser authentication, or production operation. A disposable PostgreSQL migration round-trip through revision 0029 was separately exercised; the #37 dependency-engine evaluation remains unrun.

Ticket ordering refines the task order above: capability-scoped absence (#41) depends only on #33 and #37, not on `fp.v3`.

### Carried-forward October tasks

| October task | Disposition | Where |
| --- | --- | --- |
| M07 durable dispatch | Landed in `b2065f8`; acceptance unverified | P1.3 |
| M08 fencing and durable cleanup | Partial | P1.3 (verify), remainder in P1.7 |
| M09 artifacts and atomic completion | Pilot-blocking | P1.7 |
| M10 ordered observations and decisions | Split: comparability → P1.1, identity → P1.5, capability scope → P1.6; ordered per-ref observation records deferred until shadow evidence shows the metadata series is insufficient | P1.1, P1.5, P1.6 |
| M11 GitHub ingress and reconciliation | Pilot-blocking | P2.5 |
| M12 browser workflows and honest counts | Only the shadow-results view is pilot-blocking | P2.6; remainder deferred |
| M13 revocation, erasure, restore | Deferred to pre-launch; pilot uses the disable-organization runbook | — |
| M14 legacy migration and cutover | Deferred; pilot data starts fresh | — |
| M15 operating envelope and dossier | Deferred to pre-launch; capture per-scan cost and duration during shadow (P2.6) | — |

---

## Phase 1 — Trustworthy baseline

Gate: no finding can become `fixed` because of an analyzer change, code movement, a failed unrelated scanner, or a branch-tip substitution; source acquisition ignores host Git configuration; the full API and worker unit suites pass.

### Task P1.1: Absence credit requires comparable analyzers

Fixes gap G1 in [SYSTEM_OVERVIEW](../SYSTEM_OVERVIEW.md). Today `FindingService.mark_not_observed_after_scan` counts any absence from a healthy full scan, so a scanner upgrade, rule change, parser change or fingerprint-policy change that stops reporting a finding produces two "qualifying absences" and closes it as `fixed`. ADR-014 forbids this.

**Design.** An absence earns credit only when the scanner that produced the finding ran with the same `scanner_version`, `parser_version`, `rules_digest` and fingerprint policy as at the finding's most recent presence on that branch. The baseline is derived from the stored `ScannerRun` of the most recent scan on that branch that has a `FindingInstance` for the finding. No new columns or migrations are needed. Otherwise the absence is recorded as *not credited* with a reason, and the finding stays in its current state until it is re-observed under the new analyzer or a human resolves it.

Deliberate exclusions, documented as residual risk:
- `db_digest` is not compared. Vulnerability databases refresh at least weekly (ADR-014), so requiring equality would block nearly all dependency closure. A withdrawn advisory can therefore still look like remediation for dependency findings until P1.5b adds inventory-based dependency evidence.
- `image_digest` is not compared because one image holds all scanners and is rebuilt for database refreshes.
- Compatible analyzer upgrades (declared through directional fixtures, ADR-014) are a follow-up. Until then, findings fixed across an analyzer upgrade need one human resolution.

**Files:**
- Modify: `apps/api/app/schemas/canonical_findings.py` (fingerprint constant)
- Modify: `apps/api/app/services/finding_lifecycle.py` (pure comparability rules)
- Modify: `apps/api/app/services/findings.py` (`_apply_branch_absence`, `mark_not_observed_after_scan`, two query helpers)
- Test: `apps/api/tests/test_finding_lifecycle_policy.py`
- Test: `apps/api/tests/test_findings_disappearance_scope.py` (new cases; fixture update)

**Step 1: Write the failing pure-policy tests**

Append to `apps/api/tests/test_finding_lifecycle_policy.py` (and add `ANALYZER_SIGNATURE_FIELDS`, `analyzer_comparability`, `analyzer_signature` to its import from `app.services.finding_lifecycle`):

```python
import pytest

BASE_SIGNATURE = dict(
    scanner_name="semgrep",
    scanner_version="1.90.0",
    parser_version="2026-10-parser.v1",
    rules_digest="sha256:rules-a",
    fingerprint_version="fp.v2",
)


def test_identical_analyzer_signatures_are_comparable():
    baseline = analyzer_signature(**BASE_SIGNATURE)
    current = analyzer_signature(**BASE_SIGNATURE)
    assert analyzer_comparability(baseline, current) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("scanner_name", "gitleaks"),
        ("scanner_version", "1.91.0"),
        ("parser_version", "2026-11-parser.v2"),
        ("rules_digest", "sha256:rules-b"),
        ("fingerprint_version", "fp.v3"),
    ],
)
def test_any_analyzer_change_is_not_comparable(field, value):
    baseline = analyzer_signature(**BASE_SIGNATURE)
    current = analyzer_signature(**{**BASE_SIGNATURE, field: value})
    assert analyzer_comparability(baseline, current) == AbsenceBlockReason.ANALYZER_NOT_COMPARABLE


def test_missing_baseline_is_unknown_not_comparable():
    current = analyzer_signature(**BASE_SIGNATURE)
    assert analyzer_comparability(None, current) == AbsenceBlockReason.ANALYZER_BASELINE_UNKNOWN


@pytest.mark.parametrize("field", ["scanner_version", "parser_version"])
def test_unrecorded_versions_are_never_comparable(field):
    unrecorded = analyzer_signature(**{**BASE_SIGNATURE, field: None})
    complete = analyzer_signature(**BASE_SIGNATURE)
    assert analyzer_comparability(unrecorded, unrecorded) == AbsenceBlockReason.ANALYZER_BASELINE_UNKNOWN
    assert analyzer_comparability(complete, unrecorded) == AbsenceBlockReason.ANALYZER_NOT_COMPARABLE
    assert analyzer_comparability(complete, None) == AbsenceBlockReason.ANALYZER_NOT_COMPARABLE


def test_signature_fields_exclude_database_and_image_digests():
    assert "db_digest" not in ANALYZER_SIGNATURE_FIELDS
    assert "image_digest" not in ANALYZER_SIGNATURE_FIELDS
```

**Step 2: Run them and confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_finding_lifecycle_policy.py -q`
Expected: collection error, `ImportError: cannot import name 'analyzer_comparability'`.

**Step 3: Add the fingerprint constant**

In `apps/api/app/schemas/canonical_findings.py`, add above `class CanonicalFindingCandidate` and use it as the field default:

```python
CURRENT_FINGERPRINT_VERSION = "fp.v2"
```

```python
    fingerprint_version: str = Field(default=CURRENT_FINGERPRINT_VERSION, min_length=1, max_length=32)
```

**Step 4: Implement the pure rules**

In `apps/api/app/services/finding_lifecycle.py`, add two members to `AbsenceBlockReason`:

```python
    ANALYZER_NOT_COMPARABLE = "analyzer_not_comparable"
    ANALYZER_BASELINE_UNKNOWN = "analyzer_baseline_unknown"
```

and add after `branch_obligation_counts`:

```python
ANALYZER_SIGNATURE_FIELDS = (
    "scanner_name",
    "scanner_version",
    "parser_version",
    "rules_digest",
    "fingerprint_version",
)
ANALYZER_BLOCK_KEY = "analyzer_absence_block"


def analyzer_signature(
    *,
    scanner_name: str | None,
    scanner_version: str | None,
    parser_version: str | None,
    rules_digest: str | None,
    fingerprint_version: str | None,
) -> dict[str, str | None]:
    """Identity of the analysis that produced (or failed to produce) a finding.

    Database and image digests are deliberately excluded: databases refresh
    weekly and one image carries every scanner (see the redirection plan).
    """
    return {
        "scanner_name": scanner_name,
        "scanner_version": scanner_version,
        "parser_version": parser_version,
        "rules_digest": rules_digest,
        "fingerprint_version": fingerprint_version,
    }


def _signature_recorded(signature: Mapping[str, object] | None) -> bool:
    return bool(signature and signature.get("scanner_version") and signature.get("parser_version"))


def analyzer_comparability(
    baseline: Mapping[str, object] | None,
    current: Mapping[str, object] | None,
) -> AbsenceBlockReason | None:
    """None when an absence may earn credit; otherwise why it may not.

    An absence under a different analyzer is not remediation evidence: the
    analyzer, not the code, may explain the difference (ADR-014).
    """
    if not _signature_recorded(baseline):
        return AbsenceBlockReason.ANALYZER_BASELINE_UNKNOWN
    if not _signature_recorded(current):
        return AbsenceBlockReason.ANALYZER_NOT_COMPARABLE
    for field in ANALYZER_SIGNATURE_FIELDS:
        if baseline.get(field) != current.get(field):
            return AbsenceBlockReason.ANALYZER_NOT_COMPARABLE
    return None
```

**Step 5: Run the pure tests**

Run: `.venv/bin/python -m pytest tests/test_finding_lifecycle_policy.py -q`
Expected: all pass.

**Step 6: Commit**

```bash
git add apps/api/app/schemas/canonical_findings.py apps/api/app/services/finding_lifecycle.py apps/api/tests/test_finding_lifecycle_policy.py
git commit -m "feat(lifecycle): define analyzer comparability for absence credit (P1.1)"
```

**Step 7: Update the service-test fixtures so presence scans carry analyzer evidence**

Completion persists `ScannerRun` rows before findings, but the existing `_observe` helper in `apps/api/tests/test_findings_disappearance_scope.py` creates none. In that file:

```python
TRIVY_V1 = {"scanner_version": "0.56.2", "parser_version": "2026-10-parser.v1", "rules_digest": None}
GITLEAKS_V1 = {"scanner_version": "8.21.2", "parser_version": "2026-10-parser.v1", "rules_digest": "sha256:gl-rules-a"}
OK_RUNS = (("trivy", "completed", TRIVY_V1), ("gitleaks", "completed", GITLEAKS_V1))


async def _add_runs(session, scan_id, runs):
    for name, status, signature in runs:
        session.add(
            ScannerRun(
                id=str(uuid4()),
                scan_id=str(scan_id),
                scanner_name=name,
                status=ScanStatus(status),
                **signature,
            )
        )
        # One row per flush keeps inserts single-row on both dialects.
        await session.flush()
```

Change `_observe` to accept `runs=OK_RUNS` and call `await _add_runs(session, scan.id, runs)` right after `_seed_scan`. Change `_absence` to replace its inline `ScannerRun` loop with `await _add_runs(session, scan.id, run_statuses)`. Update the two explicit `run_statuses=` tuples in existing tests to the three-element form (for example `(("trivy", "completed", TRIVY_V1), ("gitleaks", "failed", GITLEAKS_V1))`).

Run: `.venv/bin/python -m pytest tests/test_findings_disappearance_scope.py -q`
Expected: the existing tests still pass (fixture-only change).

**Step 8: Write the failing service tests**

Append to `apps/api/tests/test_findings_disappearance_scope.py`:

```python
TRIVY_V2 = {**TRIVY_V1, "scanner_version": "0.57.0"}
UPGRADED_RUNS = (("trivy", "completed", TRIVY_V2), ("gitleaks", "completed", GITLEAKS_V1))


@pytest.mark.asyncio
async def test_analyzer_upgrade_absences_never_close_finding(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-analyzer-upgrade"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    assert await _absence(service, repo_id, project_id, commit="a" * 40, run_statuses=UPGRADED_RUNS) == 0
    assert await _absence(service, repo_id, project_id, commit="b" * 40, run_statuses=UPGRADED_RUNS) == 0

    after = await _reload(db_session, finding)
    assert after.status == "open"
    series = after.metadata_json["absence_series"][MAIN]["qualifying_absences"]
    assert series == []


@pytest.mark.asyncio
async def test_uncredited_absence_is_explained_once_per_analyzer(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-analyzer-event"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    await _absence(service, repo_id, project_id, commit="a" * 40, run_statuses=UPGRADED_RUNS)
    await _absence(service, repo_id, project_id, commit="b" * 40, run_statuses=UPGRADED_RUNS)

    events = [e for e in await _events(db_session, finding) if e.event_type == "absence_not_credited"]
    assert len(events) == 1
    assert events[0].metadata_json["blocked_by"] == ["analyzer_not_comparable"]
    assert events[0].metadata_json["baseline"]["scanner_version"] == "0.56.2"
    assert events[0].metadata_json["current"]["scanner_version"] == "0.57.0"


@pytest.mark.asyncio
async def test_reobservation_under_new_analyzer_restores_credit(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-analyzer-rebaseline"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)
    await _absence(service, repo_id, project_id, commit="a" * 40, run_statuses=UPGRADED_RUNS)

    await _observe(db_session, repo_id, project_id, fingerprint, commit="1" * 40, runs=UPGRADED_RUNS)
    assert await _absence(service, repo_id, project_id, commit="b" * 40, run_statuses=UPGRADED_RUNS) == 1
    assert await _absence(service, repo_id, project_id, commit="c" * 40, run_statuses=UPGRADED_RUNS) == 1
    assert (await _reload(db_session, finding)).status == "fixed"


@pytest.mark.asyncio
async def test_finding_without_recorded_presence_analyzer_is_not_closed(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-legacy-presence"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    legacy_runs = (("trivy", "completed", {"scanner_version": None, "parser_version": None, "rules_digest": None}),)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40, runs=legacy_runs)

    assert await _absence(service, repo_id, project_id, commit="a" * 40) == 0
    assert await _absence(service, repo_id, project_id, commit="b" * 40) == 0
    assert (await _reload(db_session, finding)).status == "open"
```

**Step 9: Run them and confirm the expected failures**

Run: `.venv/bin/python -m pytest tests/test_findings_disappearance_scope.py -q`
Expected: `test_analyzer_upgrade_absences_never_close_finding` and `test_finding_without_recorded_presence_analyzer_is_not_closed` FAIL (`1 != 0`; status `not_observed`/`fixed`), and `test_uncredited_absence_is_explained_once_per_analyzer` FAILS (no events). `test_reobservation_under_new_analyzer_restores_credit` may pass today; it guards the fix.

**Step 10: Implement the service change**

In `apps/api/app/services/findings.py`, import `ANALYZER_BLOCK_KEY`, `analyzer_comparability` and `analyzer_signature` from `app.services.finding_lifecycle`, and `CURRENT_FINGERPRINT_VERSION` from `app.schemas.canonical_findings`. Add two helpers next to `_scan_has_incomplete_scanner_evidence`:

```python
    async def _scanner_signatures_for_scan(self, scan_id: str) -> dict[str, dict]:
        """Analyzer identity of every scanner that ran in this scan."""
        result = await self.db.execute(select(ScannerRun).where(ScannerRun.scan_id == scan_id))
        return {
            run.scanner_name: analyzer_signature(
                scanner_name=run.scanner_name,
                scanner_version=run.scanner_version,
                parser_version=run.parser_version,
                rules_digest=run.rules_digest,
                fingerprint_version=CURRENT_FINGERPRINT_VERSION,
            )
            for run in result.scalars().all()
        }

    async def _last_presence_signature(self, finding, branch: str) -> dict | None:
        """Analyzer identity at the finding's most recent presence on this branch."""
        if not finding.primary_scanner:
            return None
        result = await self.db.execute(
            select(ScannerRun)
            .join(FindingInstance, FindingInstance.scan_id == ScannerRun.scan_id)
            .join(Scan, Scan.id == FindingInstance.scan_id)
            .where(
                FindingInstance.finding_id == finding.id,
                Scan.branch_name == branch,
                ScannerRun.scanner_name == finding.primary_scanner,
            )
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
        run = result.scalars().first()
        if run is None:
            return None
        return analyzer_signature(
            scanner_name=run.scanner_name,
            scanner_version=run.scanner_version,
            parser_version=run.parser_version,
            rules_digest=run.rules_digest,
            fingerprint_version=finding.fingerprint_version,
        )

    def _record_uncredited_absence(self, finding, scan, branch, reason, baseline, current) -> None:
        """Explain a non-credited absence once per (branch, reason, current analyzer)."""
        metadata = dict(finding.metadata_json or {})
        blocks = dict(metadata.get(ANALYZER_BLOCK_KEY) or {})
        marker = {"reason": reason.value, "current": current}
        if blocks.get(branch) == marker:
            return
        blocks[branch] = marker
        metadata[ANALYZER_BLOCK_KEY] = blocks
        finding.metadata_json = metadata
        self.db.add(
            FindingEvent(
                finding_id=finding.id,
                event_type="absence_not_credited",
                actor_user_id=None,
                metadata_json={
                    "scan_id": str(scan.id),
                    "commit_sha": str(scan.commit_sha),
                    "branch": branch,
                    "policy": POLICY_VERSION,
                    "blocked_by": [reason.value],
                    "baseline": baseline,
                    "current": current,
                },
            )
        )
```

Change `_apply_branch_absence` to accept the scan's signatures and check comparability after the reopen-checkpoint check and before `record_qualifying_absence`:

```python
    async def _apply_branch_absence(
        self, finding, scan, branch: str, present: set[str], current_signatures: dict[str, dict]
    ) -> int:
        ...
        if scan_precedes_checkpoint(scan.created_at, metadata.get(REOPEN_CHECKPOINT_KEY)):
            # Scan issued at/before a manual reopen decision.
            return 0

        baseline = await self._last_presence_signature(finding, branch)
        current = current_signatures.get(finding.primary_scanner or "")
        block = analyzer_comparability(baseline, current)
        if block is not None:
            # An analyzer difference may explain the absence; it is not
            # remediation evidence (ADR-014).
            self._record_uncredited_absence(finding, scan, branch, block, baseline, current)
            return 0

        metadata, counted = record_qualifying_absence(
        ...
```

In `mark_not_observed_after_scan`, compute the signatures once after the incomplete-evidence check and pass them through:

```python
        current_signatures = await self._scanner_signatures_for_scan(str(scan.id))
        ...
            updated += await self._apply_branch_absence(finding, scan, branch, present, current_signatures)
```

Ensure `POLICY_VERSION` is imported in `findings.py` (it already is if the existing event code compiles; otherwise add it to the `finding_lifecycle` import).

**Step 11: Run the focused suites**

Run: `.venv/bin/python -m pytest tests/test_finding_lifecycle_policy.py tests/test_findings_disappearance_scope.py tests/test_evidence_contract.py tests/test_scan_completion.py -q`
Expected: all pass; the PostgreSQL case `test_r05_postgres_disappearance_gates` skips unless `R05_POSTGRES_URL` is set. Run it with the disposable fixture if available and record the result either way.

**Step 12: Check completion-path persistence**

While here, read `mark_not_observed_for_completed_scan` and its caller in `services/scan_completion.py`. `mark_not_observed_after_scan` commits only when `updated > 0`. Confirm the outer completion transaction commits metadata and events written when `updated == 0` (counted-but-untransitioned or not-credited absences). If it does not, record the defect in the tracker and SYSTEM_OVERVIEW; do not fix it in this slice.

**Step 13: Run the full API suite**

Run: `.venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: no new failures compared with a run on `main` before the change (record both counts).

**Step 14: Update docs and commit**

- `docs/SYSTEM_OVERVIEW.md`: mark G1 fixed in source, citing the commit; keep the `db_digest` residual risk visible.
- This plan's tracker: P1.1 `Done` with SHA and the command from Step 11.

```bash
git add apps/api/app/services/findings.py apps/api/tests/test_findings_disappearance_scope.py docs/SYSTEM_OVERVIEW.md docs/plans/2026-11-04-redirection-implementation-plan.md
git commit -m "fix(lifecycle): never credit absences under a changed analyzer (P1.1)"
```

No migration. No API contract change: the new event type is stored in existing `finding_events` rows. If the web finding timeline maps event types to labels, add `absence_not_credited` there in P2.6.

### Task P1.2: Clone isolation and exact-SHA requirement

Fixes G4 and G5. Git subprocesses inherit `HOME` and the host's system/global Git configuration, so host filter drivers, URL rewrites, `core.fsmonitor` or credential helpers apply to untrusted checkouts. When `commit_sha` is empty, `prepare_repository` clones the branch tip.

**Files:**
- Modify: `apps/worker/app/security/proc_env.py`
- Modify: `apps/worker/app/services/scan_pipeline/execution.py` (`prepare_repository`)
- Test: `apps/worker/tests/test_scanner_env_containment.py`
- Create: `apps/worker/tests/test_clone_isolation.py`

**Step 1: Write the failing tests**

Create `apps/worker/tests/test_clone_isolation.py`:

```python
"""P1.2: source acquisition ignores host Git configuration and requires an exact SHA."""
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.security.proc_env import build_git_env
from app.services.scan_pipeline.execution import ScanExecutionStage

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git binary required")


def test_git_env_disables_host_configuration(tmp_path):
    env = build_git_env(auth_header="Basic abc", home_dir=tmp_path)
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert env["HOME"] == str(tmp_path)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_LFS_SKIP_SMUDGE"] == "1"
    pairs = {
        env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"]
        for i in range(int(env["GIT_CONFIG_COUNT"]))
    }
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert pairs["core.hooksPath"] == "/dev/null"
    assert pairs["protocol.allow"] == "never"
    assert pairs["protocol.https.allow"] == "always"
    assert "protocol.file.allow" not in pairs


def test_git_env_allows_file_protocol_only_when_requested(tmp_path):
    env = build_git_env(auth_header="", home_dir=tmp_path, allow_file_protocol=True)
    pairs = {
        env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"]
        for i in range(int(env["GIT_CONFIG_COUNT"]))
    }
    assert pairs["protocol.file.allow"] == "always"
    assert "http.extraHeader" not in pairs


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def hostile_fixture(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-q")
    _git(source, "config", "user.email", "fixture@example.invalid")
    _git(source, "config", "user.name", "fixture")
    (source / ".gitattributes").write_text("*.txt filter=hostile\n")
    (source / "a.txt").write_text("content\n")
    _git(source, "add", ".")
    _git(source, "commit", "-q", "-m", "fixture")
    sha = _git(source, "rev-parse", "HEAD")

    marker = tmp_path / "host-filter-ran"
    fake_home = tmp_path / "host-home"
    fake_home.mkdir()
    (fake_home / ".gitconfig").write_text(
        f'[filter "hostile"]\n\tsmudge = sh -c \'touch {marker}; cat\'\n'
    )
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SCANFORGE_ALLOW_LOCAL_GIT_FIXTURES", "1")
    monkeypatch.setenv("WORKER_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    return source, sha, marker


def _stage(clone_url: str) -> ScanExecutionStage:
    stage = ScanExecutionStage(r2=AsyncMock(), api_base_url="http://api.test", worker_credential="w")
    stage._get_clone_url = AsyncMock(return_value=(clone_url, ""))
    return stage


@pytest.mark.asyncio
async def test_host_git_filter_does_not_run_on_checkout(hostile_fixture):
    source, sha, marker = hostile_fixture
    stage = _stage(source.resolve().as_uri())
    repo_dir = await stage.prepare_repository(
        SimpleNamespace(scan_id="s1", attempt_id="a1", repository_id="r1", commit_sha=sha, branch=None)
    )
    try:
        assert (repo_dir / "a.txt").read_text() == "content\n"
        assert not marker.exists(), "host-defined Git filter executed during checkout"
    finally:
        shutil.rmtree(repo_dir.parent, ignore_errors=True)


@pytest.mark.asyncio
async def test_missing_commit_sha_is_refused(hostile_fixture):
    source, _sha, _marker = hostile_fixture
    stage = _stage(source.resolve().as_uri())
    with pytest.raises(RuntimeError, match="exact commit SHA is required"):
        await stage.prepare_repository(
            SimpleNamespace(scan_id="s2", attempt_id="a1", repository_id="r1", commit_sha=None, branch="main")
        )
```

**Step 2: Run them and confirm they fail**

Run: `.venv/bin/python -m pytest tests/test_clone_isolation.py -q`
Expected: `ImportError: cannot import name 'build_git_env'`. After adding a stub, the filter test fails with `host-defined Git filter executed during checkout` and the refusal test fails because the branch clone path runs.

**Step 3: Implement `build_git_env`**

Append to `apps/worker/app/security/proc_env.py`:

```python
from pathlib import Path


def build_git_env(*, auth_header: str, home_dir: Path, allow_file_protocol: bool = False) -> dict[str, str]:
    """Environment for git subprocesses that operate on untrusted repositories.

    Host system/global configuration (filter drivers, URL rewrites, fsmonitor,
    credential helpers) must not apply, and only HTTPS transport is allowed.
    The auth header, when present, is always config index 0 so callers can
    scrub GIT_CONFIG_VALUE_0 after use.
    """
    config: list[tuple[str, str]] = []
    if auth_header:
        config.append(("http.extraHeader", auth_header))
    config += [
        ("core.hooksPath", "/dev/null"),
        ("core.fsmonitor", "false"),
        ("protocol.allow", "never"),
        ("protocol.https.allow", "always"),
    ]
    if allow_file_protocol:
        config.append(("protocol.file.allow", "always"))

    env = build_contained_env(
        {
            "HOME": str(home_dir),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_CONFIG_COUNT": str(len(config)),
        }
    )
    for index, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    return env
```

**Step 4: Use it in `prepare_repository` and refuse missing SHAs**

In `apps/worker/app/services/scan_pipeline/execution.py`:

1. Import `build_git_env` from `app.security.proc_env`.
2. Replace the `git_env = build_contained_env({...})` block with:

```python
        git_home = repo_dir.parent / "git-home"
        git_home.mkdir(mode=0o700, exist_ok=True)
        git_env = build_git_env(
            auth_header=auth_header,
            home_dir=git_home,
            allow_file_protocol=allow_local_fixture,
        )
```

3. Immediately after `expected_sha` is computed and before `try:`, add:

```python
        if not expected_sha:
            shutil.rmtree(repo_dir.parent, ignore_errors=True)
            raise RuntimeError("exact commit SHA is required; refusing to scan a branch tip")
```

4. Delete the now-unreachable `else:` branch (the `git clone --single-branch` block through its `raise RuntimeError(f"git clone failed: ...")`) and dedent the former `if expected_sha:` body.
5. Keep the existing `finally` scrub of `GIT_CONFIG_VALUE_0`.

**Step 5: Update the existing containment test**

In `apps/worker/tests/test_scanner_env_containment.py::test_git_clone_environment_is_allowlisted`, pass a SHA so the exact-fetch path runs, and widen the allowed extras to the new keys:

```python
        repo_dir = await stage.prepare_repository(
            SimpleNamespace(scan_id="scan-1", attempt_id="a1", repository_id="repo-1", commit_sha="a" * 40, branch=None)
        )
```

Set `GIT_AUTH_KEYS` to the keys produced by `build_git_env` with an auth header (indexes 0–4 plus `GIT_CONFIG_COUNT`, `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL`, `GIT_TERMINAL_PROMPT`, `GIT_LFS_SKIP_SMUDGE`), replace `assert env.get("GIT_CONFIG_COUNT") == "1"` with `assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"`, and add `assert env["HOME"] != os.environ.get("HOME")`. Because the recorded fake `subprocess.run` returns empty stdout, also assert the call sequence starts with `git init` and that `prepare_repository` raises at SHA verification, wrapping the call in `pytest.raises(RuntimeError)`. Keep the environment assertions on `captured[0]`.

**Step 6: Find and fix other callers relying on the branch-tip path**

Run: `grep -rn "prepare_repository\|commit_sha=None\|branch=" tests/test_scan_orchestrator.py tests/test_lease_renewer.py`
Give every fixture context that reaches `prepare_repository` a `commit_sha`. A test that asserted branch-tip cloning is now asserting the defect; change it to expect the refusal.

**Step 7: Verify the API never dispatches without a SHA**

From `apps/api`, read `tests/test_execution_context_identity.py` and `services/scan_lifecycle.py`. Confirm that the execution context for manual and push scans carries a resolved `commit_sha` (M06). If a path can dispatch without one, record it as a blocker in the tracker; the worker refusal is correct either way.

**Step 8: Run the suites**

Run (worker): `.venv/bin/python -m pytest tests/test_clone_isolation.py tests/test_scanner_env_containment.py tests/test_scan_orchestrator.py -q`, then the full worker unit suite: `.venv/bin/python -m pytest -q -p no:cacheprovider --ignore=tests/test_real_scanner_fixtures.py --ignore=tests/test_redis_stream_recovery_integration.py`
Expected: all pass. Real-scanner and Redis suites are recorded as not run unless their fixtures are available.

**Step 9: Update docs and commit**

Mark G4/G5 fixed in `docs/SYSTEM_OVERVIEW.md` and update the tracker.

```bash
git add apps/worker/app/security/proc_env.py apps/worker/app/services/scan_pipeline/execution.py apps/worker/tests/test_clone_isolation.py apps/worker/tests/test_scanner_env_containment.py docs/SYSTEM_OVERVIEW.md docs/plans/2026-11-04-redirection-implementation-plan.md
git commit -m "fix(worker): isolate git from host config and require exact SHAs (P1.2)"
```

Also stage any orchestrator test fixtures changed in Step 6. Changing the provisioning script is out of scope; host Git configuration no longer matters to scans after this task.

### Task P1.3: Verify carried-forward M07/M08 acceptance

No new behavior. Turn "landed in code" into evidence or into explicit gaps.

- Run the M07 check with real PostgreSQL concurrency: `.venv/bin/python -m pytest tests/test_scan_dispatch.py tests/test_scan_lifecycle.py tests/test_webhook_route_security.py -q` (API) against the disposable fixture (`infra/testing/docker-compose.integration.yml` or native PostgreSQL 16 per [RUNNING_LOCALLY](../../RUNNING_LOCALLY.md)).
- Walk the archived October M07 and M08 checklists item by item. For each item, cite the test that proves it or mark it missing.
- Missing M07 items become sub-tasks here. Missing M08 fencing items (progress, findings, uploads, heartbeat routes, not only completion) become sub-tasks here. M08 cleanup durability moves to P1.7.

#### M07 acceptance evidence (#35)

Tests are in `apps/api/tests/test_scan_dispatch.py` (SQLite, queue emulator) and `apps/api/tests/test_scan_dispatch_postgres.py` (disposable PostgreSQL 16, real concurrency; skipped when no PostgreSQL binaries or `DISPATCH_POSTGRES_URL`/`R04_POSTGRES_URL` are available).

| M07 checklist item | Status | Evidence |
| --- | --- | --- |
| Queue outage after scan creation retains an awaiting-dispatch obligation and recovers on retry | Proven | `test_queue_outage_retains_awaiting_dispatch_and_recovers_on_retry` |
| Crash after queue delivery before acknowledgement is idempotent on reclaim | Proven | `test_crash_after_queue_delivery_before_ack_is_idempotent_on_reclaim` |
| Trigger, scan and obligation persist in one transaction | Proven (scan + obligation); fixed (savepoint) | `test_scan_and_obligation_commit_or_roll_back_together`. Fixed: a losing duplicate used `rollback()` on the caller's session, discarding the webhook delivery row and expiring loaded rows; `ScanService.create` now isolates scan + obligation insert in a savepoint |
| Idempotent leased dispatcher with retries and visible awaiting-dispatch state | Proven | `test_postgres_concurrent_dispatchers_claim_each_obligation_once_with_zero_stranded`, `test_dispatcher_restart_reclaims_expired_lease_and_delivers_once`, outage test above |
| Equivalent automatic business identity incl. scope/coverage context | Proven | `test_automatic_business_identity_and_manual_idempotency_vs_deliberate_rerun`, `test_concurrent_duplicate_automatic_triggers_yield_one_scan_and_one_obligation` |
| Manual request idempotency separate from deliberate reruns | Fixed + proven | `test_concurrent_manual_requests_split_idempotent_duplicates_from_deliberate_reruns` (concurrent same-key requests previously raised `MissingGreenlet`) |
| Bounded admission | Proven (SQLite) | `test_bounded_admission_and_explicit_supersession_of_unstarted_automatic_work` |
| Explicit supersession of unstarted automatic work within a generation; manual work never coalesced | Proven | same test; `test_burst_with_concurrent_dispatchers_leaves_no_stranded_obligation` (manual scan survives a burst) |
| Concurrent dispatchers, duplicates, restarts and bursts: one authoritative scan per equivalent trigger, zero stranded obligations | Fixed + proven on PostgreSQL | the three PostgreSQL tests above. Fixed: concurrent first pushes to a ref raced on `uq_repo_branch_generation` (500); `RepositoryRefService.resolve_and_advance_generation` now takes a per-ref `pg_advisory_xact_lock` so ref transitions, the scan and its obligation serialize |

Not run: real Upstash Redis (the queue path uses the in-memory emulator `InMemoryUpstashQueue`); the Docker integration stack (`infra/testing/docker-compose.integration.yml`) because Docker is not accessible to this user, so a native PostgreSQL 16 cluster was used instead.

Acceptance: a table in this plan listing every M07/M08 checklist item as proven (with test) or open. Commit the table only (`docs: verify M07/M08 acceptance (P1.3)`).

### Task P1.4: Primary dependency engine evaluation

Three engines (Trivy, OSV-Scanner, Grype) produce overlapping dependency findings with identical fingerprints (G3). Choose one primary before fixing identity, so P1.5 does not have to solve cross-scanner equivalence for three engines.

- Build a fixture corpus under `apps/worker/tests/fixtures/dependency_eval/`. It needs synthetic or appropriately licensed lockfiles covering npm (`package-lock.json`), PyPI (`requirements.txt`, `poetry.lock`), and a monorepo with the same package in two manifests. Include known-vulnerable pinned versions and clean versions.
- Run each engine from the pinned scanner image, offline, against the corpus. Record per engine: supported inputs, true and false positives against the known list, advisory ID scheme (CVE/GHSA/OSV), whether manifest path and ecosystem are reported, fixed-version data, offline behavior, runtime and memory, and license.
- Write the result to `docs/reviews/2026-11-dependency-engine-evaluation.md` with a recommendation. Record the decision as ADR-019.
- Change `SCAN_MODE_REGISTRY` in [registry.py](../../apps/worker/app/scanners/registry.py) so the default full scan runs the primary dependency engine plus Syft (inventory). Keep the other adapters registered but not run by default.

Acceptance: evaluation document with raw counts; ADR-019 accepted by you; registry change with a test asserting the default scanner set; full worker suite passes.

### Task P1.5: Fingerprint policy `fp.v3`

Fixes G2 and G3 per ADR-014. Bump `CURRENT_FINGERPRINT_VERSION` to `fp.v3`. P1.1 then guarantees that findings created under `fp.v2` are never closed by `fp.v3` absences.

- **Source findings (Semgrep, Checkov):** identity = repository + rule ID + normalized path + a hash of the normalized matched snippet (whitespace-collapsed) + an occurrence index among identical snippets in the same file. Line numbers move to the occurrence record only.
- **Secrets (Gitleaks):** identity = repository + rule ID + normalized path + occurrence index among same-rule matches in the file. Never derive identity from the secret value or anything containing it (ADR-014, Round 2 Q8).
- **Dependencies:** identity = repository + ecosystem + package + installed version + advisory ID + scanner. Cross-scanner merging only through an explicit, tested equivalence table, which is empty initially. With one primary engine (P1.4) this is mostly moot.
- **Migration:** additive. Existing findings keep `fp.v2` and their history. New observations create `fp.v3` findings. A one-time link step may connect an `fp.v3` finding to an `fp.v2` predecessor only when the rule, path and snippet hash match exactly. It records `predecessor_finding_id` in metadata and never transfers human dispositions automatically. `fp.v2` findings that are not re-observed stay open with the `analyzer_not_comparable` explanation from P1.1, and the UI must show this.
- **Tests:** a moved line keeps identity; two identical snippets in one file stay distinct; a snippet edit creates a new identity; the same package in npm and PyPI never collides; Trivy and OSV results for one advisory stay separate without an equivalence entry; secret fixtures contain no secret-derived material in any fingerprint.

Acceptance: the tests above, the full API and worker suites, and the before/after finding counts on the evaluation corpus recorded in the tracker.

**P1.5b (follow-up):** for dependency findings, credit an absence only when inventory (Syft) shows that `package@version` is no longer present at that path. An advisory disappearing while the package version is still installed is an intelligence change, not remediation. This closes the `db_digest` residual risk from P1.1.

### Task P1.6: Capability-scoped absence

Fixes G6. Today absence credit needs all expected scanners healthy.

- Map scanners to capabilities: secrets (Gitleaks), SAST (Semgrep), dependencies (P1.4 primary engine plus Syft), IaC (Checkov). Put this map next to `SCAN_MODE_REGISTRY` and mirror it in the API evidence contract.
- `evaluate_scan_absence_evidence` takes the finding's capability. Absence for a finding is eligible when that capability's scanners completed healthy, independent of other capabilities.
- A capability whose scanner failed contributes no absence evidence for its findings. An unrelated success never proves its absence.

Acceptance: a Checkov failure does not block secret reassessment and grants no IaC absence; existing disappearance tests pass; the PostgreSQL variant is run or recorded as not run.

### Task P1.7: Artifact finalization and server-derived completion

Carries the October M09 checklist (archived plan, Task M09) unchanged in substance. It also carries the M08 cleanup-durability items that P1.3 found open. Expand into steps when started; the archived checklist and checks are the acceptance criteria.

### Task P1.8: Coverage assessment record

Extend the M03 evidence contract ([evidence_contract.py](../../apps/api/app/services/evidence_contract.py)) with an additive per-capability coverage record: declared scope; inputs found and supported; unsupported inputs (for example lockfile types the engine cannot parse); exclusions; parse failures; truncation; timeouts; and a state of `complete` / `partial` / `unknown` / `not_applicable` with reasons. `not_applicable` requires evidence, for example that no IaC files were found. Coverage comes only from what the analyzer actually reports. Never invent percentages.

Acceptance: contract tests for each state; OpenAPI and web types regenerated; the scan detail API exposes coverage per capability.

---

## Phase 2 — Shadow PR review

Gate (P2.7): on ScanForge's own repository and two design-partner repositories, shadow results for real PRs are recorded with correct base, head and merge-base, labelled new/existing/unknown against a comparable baseline, reconciled across force-pushes and rapid pushes without duplicates, and reviewed by a human for usefulness. Nothing is published to GitHub. Expand each task into executable steps when it starts.

### Task P2.1: PR revision identity and baseline comparison

- On `pull_request` events, resolve and persist base SHA, head SHA and merge-base. Record the comparison strategy explicitly: head scan compared with the merge-base scan.
- A finding is **new** only when a comparable baseline exists for the merge-base (same capability coverage, comparable analyzers per P1.1). With no comparable baseline it is **unknown**; schedule baseline work rather than treating the base as clean.
- Analyze the full repository at head and filter what is presented. Do not assume a changed-files-only scan is equivalent.
- Add a `pr_shadow` server capability, separate from `pr_review` (publication), so shadow execution can be enabled per organization while publication stays disabled.

### Task P2.2: Shadow PR analysis on ScanForge's own repository

- Debounce rapid pushes. Supersede obsolete head runs, reusing M07 supersession semantics.
- Fork PRs: no privileged credentials and no execution of fork-provided configuration.
- Record per run: revisions, coverage, results by new/existing/unknown, duration and runner cost estimate.
- Enable `pr_shadow` for ScanForge's own organization only.

### Task P2.3: Cross-commit reconciliation

- A shadow "comment candidate" record (PR, head SHA, finding or observation link, location, state: active/outdated/resolved/superseded) is created, updated or superseded across pushes instead of duplicated.
- Handle force-push, rebase and webhook redelivery idempotently. An outdated candidate is not a verified fix.

### Task P2.4: One framework review pack (FastAPI)

- FastAPI is first because ScanForge's own API is a FastAPI service.
- Pack contents: detection (FastAPI app/router present), context-retrieval recipe (dependencies that establish identity and organization scope, for example `Depends(...)` auth helpers), curated Semgrep rules for tenant-scope and authorization questions, fixtures with legitimate patterns that must not fire, and unsupported cases.
- Tested context strategy only. It is not a claim of comprehensive detection.

### Task P2.5: GitHub ingress reconciliation (carried M11)

Carries the October M11 checklist: server-derived integration, installation/repository lifecycle events, reconciliation of missed events. Adds `pull_request` event routing into P2.1. Live App delivery needs a non-production GitHub App; record it as verifier-blocked until you supply one.

### Task P2.6: Shadow results view and evaluation corpus

- Internal dashboard view per PR: revisions, coverage, new/existing/unknown results, limitations, cost and duration.
- Reviewers label each candidate useful / not useful / incorrect / duplicate / missing context. Labels are evaluation data, not suppressions.
- Retain labelled snapshots as the replay corpus for Phase 3, within tenant retention rules. Keep a held-out split.
- Add timeline labels for `absence_not_credited` (P1.1).

### Task P2.7: Pilot gate

Two design-partner repositories plus ScanForge, each with at least two weeks of shadow PR results reviewed. Phase 3 thresholds are set from this data. Decide with you whether to publish advisory Checks; enabling `pr_review` publication requires its own ADR.

---

## Phase 3 and later (deferred, expand into separate plans)

- **P3:** one bounded contextual reviewer as a separate ADR-017 job (never inline in scans), using the P2.6 corpus and labels for evaluation against the scanner-only baseline. Then advisory Check publication, structured feedback, dependency paths and intelligence enrichment. Thresholds come from P2.7 data; the October ">=90% precision / >=80% recall" figure is a candidate only (ADR-018).
- **P4:** selective reachability, bounded fix suggestions, exports, more framework packs, stronger merge policy, and an answer to the open question from ADR-018 about how the dedicated-host model scales economically to small teams.
- **Pre-launch (deferred October work):** M13 erasure and tombstone-aware restore, M14 legacy migration and cutover, M15 operating envelope and release dossier. Commercial privacy, subprocessor and trust disclosures remain launch prerequisites.

## Open questions to resolve during execution

1. ~~Do counted-but-untransitioned absences reach the database in the completion path (P1.1 Step 12)?~~ Yes; see the P1.1 tracker row. The `commit=True` path's latent gap remains.
2. Does the nested `scanforge-security-platform/.github/` Dependabot/Renovate configuration run at all? If not, move it to the Git root `.github/` in a separate change.
3. B11 (`/findings/trend` shadowing) appears open; confirm with an assembled-router test and fix as a small independent slice.
4. 19 harness stashes, about 25 stale branches and two prunable worktrees need a separate, approval-gated Git housekeeping inventory.
