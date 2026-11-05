# M05 — Every shipped scanner executes; redacted findings preserved

Track: worker. Depends on: M04. Status: brief ready; spawn gated on M04.

## GOAL

All seven registered scanners run real pinned executables against real reports, normalize their evidence without losing it, and never persist raw secret data or canary leakage.

## SCOPE

Work in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/scanforge-security-platform` on the integration branch at its current head.

- Modify: `apps/worker/app/scanners/` (base, registry, trivy, gitleaks, osv, semgrep, syft, checkov, grype), their normalizers, `apps/worker/app/security/secret_evidence.py`, `app/security/redaction.py` (corrupted dead regex — fix regression-first), `app/services/scan_pipeline/execution.py`, `normalization.py`, `apps/worker/Dockerfile.scanners`.
- Create: `apps/worker/tests/test_real_scanner_fixtures.py` and sanitized fixtures under `apps/worker/tests/fixtures/scanners/`.
- Tests: extend `test_scanners.py`, `test_normalizers.py`, `test_secret_boundaries.py`.

## CONTEXT

- Plan authority: task M05 in the managed-beta plan; ADR-017 in the shared tree docs/adr/, read-only.
- Convention map: `orchestrate/managed-beta/reports/exp-worker.md`. Verified facts: only trivy and gitleaks implement `runtime_arguments()`/`parse_runtime_result()` today; osv, semgrep, syft, checkov, grype would only run `--version` contained; semgrep uses `--config auto` (network) which the no-network runtime forbids; gitleaks raw output is dropped entirely; host-vs-pin version divergences exist (osv-scanner 1.9.2 vs 2.3.3, gitleaks 8.30.1 vs 8.30.0, checkov unpinned locally).
- Docker absent on this host (gate `docker-runtime`). Version-exact evidence comes from downloading the pinned binaries into the gitignored fixture dir, not from images. Image-fixture execution stays `verifier-blocked` with the gate named.

## ACCEPTANCE

1. Regression-first: a test proves gitleaks findings survive the actual execution → upload → normalization order today (it fails), then the fix makes it pass. Same pattern for trivy sanitization idempotency preserving rule and location, and for the corrupted `redaction.py` regex.
2. Missing contained commands or parsers fail explicitly with a documented error; no scanner silently returns empty evidence.
3. One adapter at a time, each proven against five report shapes from the pinned executable: positive, empty, malformed, truncated, timeout.
4. Safe evidence is normalized before raw secret data is discarded; outputs are retained through upload/persistence then cleaned; every fixture embeds canary strings and each adapter's outputs, logs, and persisted artifacts are asserted canary-free.
5. Version, rules and database identity come from the executing manifest, not hardcoded strings; freshness is enforced; severity and confidence stay separate; conflicting provider values are preserved, not merged.
6. Pinned binaries for all seven are fetched into the gitignored fixture bin dir (osv-scanner 2.3.3, gitleaks 8.30.0, trivy 0.69.3, semgrep 1.156.0, syft 1.42.3, grype 0.110.0, checkov 3.2.513) and the suite runs against them; any fetch failure records the affected cases `verifier-blocked` honestly.
7. semgrep runs from a pinned offline rules pack in the fixtures, no network.
8. Image-based fixture execution is recorded `verifier-blocked: docker-runtime`; per-adapter and shared-boundary commits, enumerated paths only, SHAs via rev-parse.

## VERIFY

- `cd apps/worker && .venv/bin/python -m pytest tests/test_normalizers.py tests/test_secret_boundaries.py tests/test_real_scanner_fixtures.py -q`.
- `.venv/bin/python -m pytest tests/test_scanners.py -q`.
- Canary grep across persisted fixture outputs pasted into the report.
- `git show --stat` per commit.

## TIMEBOX

3 hours. FORBIDDEN: network at scan time, canary leakage in committed fixtures (canaries live in tests, fixtures stay sanitized), removing a scanner without an advertised-coverage adjustment, credential literals, edits outside enumerated paths.

## REPORT

Status, branch, per-commit SHAs, per-scanner fixture matrix (five shapes each), canary evidence, blocked list with gate ids, deviations, follow-ups.
