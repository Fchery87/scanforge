# Dependency engine evaluation corpus

Synthetic lockfiles for comparing Trivy, OSV-Scanner and Grype (with Syft as inventory reference). See [ADR-019](../../../../../docs/adr/ADR-019-primary-dependency-engine.md) and the [evaluation write-up](../../../../../docs/reviews/2026-11-dependency-engine-evaluation.md).

- `cases/` holds one directory per case. Each is a self-contained repository root to mount read-only as `/workspace/source`.
- `ground_truth.json` lists, per case, which `package@version` pins must be reported (`expect_vulnerable`) and which must not (`expect_clean`). Advisory IDs there are author-asserted and informational; scoring is by package and version.
- The lockfiles are hand-written minimal files: no integrity hashes, an all-zero Poetry `content-hash`, and `files = []`. They are meant to be read by scanners, never installed. Nothing here is a real project and nothing may be installed from it.
- The vulnerable pins are intentionally old. Renovate is told to ignore this directory (`.github/renovate.json`).

Run the harness (needs the pinned scanner image and a Docker host; not run as of 2026-11-05):

```text
python scripts/evaluate_dependency_engines.py plan      # write a results skeleton, every cell NOT RUN
python scripts/evaluate_dependency_engines.py run       # real scanners; needs Docker + SCANNER_IMAGE
python scripts/evaluate_dependency_engines.py render    # results JSON -> markdown tables
```
