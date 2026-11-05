# ADR-019: Primary dependency engine

## Status

Accepted-provisional on 2026-11-05 by maintainer decision. Supersedable: a later ADR that records the corpus evaluation, or any ADR that changes the engine, replaces this one without needing to argue against it.

**The charter's "chosen by evaluation" step was skipped.** The product charter and plan task P1.4 require the primary dependency engine to be chosen after running Trivy, OSV-Scanner and Grype against a fixture corpus from the pinned scanner image, offline. That evaluation has not been run. No Docker host was available. The maintainer approved Trivy plus Syft provisionally rather than wait. Everything below the Decision is reasoning from the repository and from tool documentation, not a measurement. The evaluation corpus and harness exist ([fixtures](../../apps/worker/tests/fixtures/dependency_eval/), [harness](../../scripts/evaluate_dependency_engines.py), [write-up](../reviews/2026-11-dependency-engine-evaluation.md)), and every real-scanner result there is marked NOT RUN.

## Context

Trivy, OSV-Scanner and Grype all ran on every full scan and reported overlapping dependency findings. Their normalizers use the same dependency fingerprint inputs, which implicitly merges cross-scanner results ([SYSTEM_OVERVIEW](../SYSTEM_OVERVIEW.md) gap G3; ADR-014 requires tested equivalence before merging). Choosing one primary engine first lets fingerprint policy `fp.v3` (#39) and capability-scoped absence (#41) be designed for one dependency engine instead of three, and reduces full-scan runtime and the number of database-backed scanners that must be fresh for a scan to count as complete.

## Decision

1. **Trivy is the primary dependency engine** and **Syft supplies inventory**. The default full scan runs Trivy, Syft, Gitleaks, Semgrep and Checkov.
2. **OSV-Scanner and Grype stay registered** (adapters, normalizers, image contents) but are not part of the default full scan. Explicit dependency scans (`scan.dependencies` / `dependencies`) are unchanged and still run Trivy, OSV-Scanner, Syft and Grype. Narrowing that mode is deliberately left to the evaluation outcome.
3. The change is made in three places that must agree: the worker `SCAN_MODE_REGISTRY` and the two API expected-scanner tables (`internal.py`, `repository_refs.py`). Tests pin each side.
4. This decision is provisional until the verification below is recorded.

## Rationale (reasoned, not measured)

- Trivy was already in every scan set and is the only candidate that also contributes to non-dependency categories, so keeping it adds no scanner and removing it would not.
- Trivy's report carries, per vulnerability, the package name, installed version, fixed version and the lockfile target it came from, which are the fields the dependency identity in ADR-014 needs (ecosystem/package, version, advisory, manifest occurrence). The adapter and normalizer already exist and are tested against synthetic reports.
- One engine reading one database removes two of three database-backed scanners from the completeness requirement for a full scan.
- All three engines are open source (Apache-2.0 per their projects; confirm against the pinned versions' LICENSE files during the evaluation).

These are plausible, not demonstrated. OSV-Scanner reads OSV's own, often better-attributed advisory data, and Grype is strong on distro and image packages; either may beat Trivy on this corpus.

## What a later corpus run must verify

Run `python scripts/evaluate_dependency_engines.py run` on a Docker host with the digest-pinned scanner image and record the result in the evaluation write-up. Trivy keeps the role only if all of these hold; otherwise a new ADR must supersede this one.

1. Every `expect_vulnerable` pin is reported by Trivy in all three lockfile styles (`package-lock.json`, `requirements.txt`, `poetry.lock`) and in the monorepo case once per manifest path (two occurrences of lodash 4.17.15, none for the clean manifest).
2. No `expect_clean` pin is reported, after hand-checking each hit against current advisories.
3. Trivy reports the manifest path and ecosystem for each finding, and fixed-version data where an advisory has one.
4. Trivy runs offline with `--network=none` using only the baked database and does not degrade silently when the database is stale or missing.
5. Trivy's advisory ID scheme is recorded (CVE, GHSA or both) and is stable enough to be an input to `fp.v3`.
6. Runtime and peak memory are recorded for each engine, with Trivy no worse than an agreed bound.
7. Any true positive found by OSV-Scanner or Grype but missed by Trivy is listed. A material miss is grounds to supersede.

The evaluation should also answer whether explicit dependency scans should keep running all four scanners.

## Consequences

- Plan tasks P1.5/#39 (`fp.v3`) and P1.6/#41 (capability-scoped absence) are unblocked on the assumption of a single dependency engine. If this ADR is superseded, they must be revisited.
- Scans created before deployment carry the old seven-scanner expectation. The worker no longer runs OSV-Scanner or Grype for them, so the server records them as missing expected scanners, partial coverage and ineligible for closure. That is the safe direction: it can delay closure but cannot create false closure. New scans use the five-scanner expectation.
- Findings last observed by OSV-Scanner or Grype are not credited with absence by a Trivy run when absence credit requires a comparable analyzer (ADR-014, P1.1). Such findings can stay open until re-observed or triaged by hand. How many exist in practice is not measured.
- Coverage the default scan loses until the evaluation runs is unknown. Vulnerabilities that only OSV-Scanner or Grype would have reported are no longer found by default full scans. Explicit dependency scans still include them.
- Trivy's adapter also runs secret and misconfiguration scanning (`--scanners vuln,secret,misconfig`), overlapping Gitleaks and Checkov. That overlap is unchanged by this ADR and is not evaluated.
- The scanner image still contains all tools, and the pinned-image verification still exercises all seven adapters.
