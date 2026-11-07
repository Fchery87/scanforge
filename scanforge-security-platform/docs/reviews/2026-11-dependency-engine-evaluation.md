# Dependency engine evaluation (P1.4, #37)

Status: **NOT RUN.** No real scanner has been executed for this evaluation. The corpus and harness are built and unit-tested on synthetic reports; every per-engine result below is a placeholder. [ADR-019](../adr/ADR-019-primary-dependency-engine.md) records the provisional decision made without these results.

Why not run: no Docker host was available to the author, and the evaluation must run each engine from the digest-pinned scanner image, offline.

## What exists

| Item | Location | State |
| --- | --- | --- |
| Corpus: 7 cases (npm lockfile vulnerable and clean; PyPI `requirements.txt` vulnerable and clean; Poetry vulnerable and clean; npm monorepo with the same vulnerable package in two manifests plus a clean third) | [dependency_eval](../../apps/worker/tests/fixtures/dependency_eval/) | Written. Hand-made minimal lockfiles; never installed |
| Ground truth (`expect_vulnerable` / `expect_clean` per case) | [ground_truth.json](../../apps/worker/tests/fixtures/dependency_eval/ground_truth.json) | Author-asserted from public advisory knowledge, not verified against any scanner database |
| Harness (`plan`, `run`, `render`) | [evaluate_dependency_engines.py](../../scripts/evaluate_dependency_engines.py) | Extraction, scoring, plan and render unit-tested on synthetic reports ([tests](../../scripts/test_evaluate_dependency_engines.py)). The `run` path has never executed against Docker |
| Results skeleton | [results JSON](2026-11-dependency-engine-evaluation-results.json) | Every cell NOT RUN |

## How to run it

On a Docker host, with the repository checked out and the worker virtualenv available:

```text
export SCANNER_IMAGE=<digest-pinned scanner image>   # plus the worker runtime settings build_scan_runtime() needs
python scripts/evaluate_dependency_engines.py run --results docs/reviews/2026-11-dependency-engine-evaluation-results.json
python scripts/evaluate_dependency_engines.py render > /tmp/tables.md
```

`run` drives each engine through the worker's contained Docker runtime (`adapter.run_contained`), so it uses the same network-disabled, read-only, resource-limited container as production and writes raw per-cell output next to the results file. Then replace the NOT RUN sections below with the rendered tables and the hand-recorded measurements, and re-check each true/false positive by hand.

Hand-recorded because the harness does not capture them: peak memory (sample `docker stats` or the container's cgroup `memory.peak`), confirmation that no network was attempted, and behaviour with a stale or missing database.

## Results by criterion

Every cell is **NOT RUN**.

| Criterion (from the issue) | Trivy | OSV-Scanner | Grype | Syft (inventory) |
| --- | --- | --- | --- | --- |
| Supported inputs: `package-lock.json` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Supported inputs: `requirements.txt` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Supported inputs: `poetry.lock` | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| True positives (of 8 expected vulnerable pins across 4 cases) | NOT RUN | NOT RUN | NOT RUN | n/a |
| False positives on clean pins (of 7 clean pins; hand-check each) | NOT RUN | NOT RUN | NOT RUN | n/a |
| Advisory ID scheme (CVE / GHSA / OSV) | NOT RUN | NOT RUN | NOT RUN | n/a |
| Manifest path reported | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Ecosystem reported | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Fixed-version data | NOT RUN | NOT RUN | NOT RUN | n/a |
| Monorepo: both occurrences of lodash 4.17.15 reported with distinct manifests | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Offline behaviour (database baked in, no network, stale or missing database) | NOT RUN | NOT RUN | NOT RUN | n/a |
| Runtime | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Peak memory | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Licence (read from the pinned version's LICENSE file) | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

Pin counts: vulnerable pins are 2 (`npm-vulnerable`), 2 (`pypi-requirements-vulnerable`), 2 (`pypi-poetry-vulnerable`) and 2 (`monorepo-duplicate`, one per manifest), total 8. Clean pins are 2, 2, 2 and 1 (monorepo manifest c), total 7.

## Raw per-engine results

NOT RUN. Raw reports go to `docs/reviews/2026-11-dependency-engine-evaluation-results-raw/` when the harness runs.

## Recommendation

None from this document, because nothing was measured. The provisional decision (Trivy primary, Syft inventory) comes from the maintainer and is recorded in ADR-019 with the conditions a real run must meet.
