# EXP-WORKER — Convention map of apps/worker for the managed-beta worker track

Read-only investigation. GOAL: give the coordinator everything needed to author precise M04 and M05 briefs without re-reading the codebase.

Map, in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/apps/worker` (branch `managed-beta/integration`):

1. Runtime: files in `app/runtime/` (base, docker, containment, models), what each provides, how the docker runtime is invoked, and what happens without docker today (fallback behavior).
2. Main loop: `app/worker/main.py` and `app/worker/maintenance.py`, how scans are consumed from Redis Streams, concurrency model.
3. Scan pipeline: `app/services/scan_pipeline/` stages (execution, normalization, persistence), what each stage assumes about workspaces and artifacts.
4. Scanners: each module in `app/scanners/` (base, registry, trivy, gitleaks, osv, semgrep, syft, checkov, grype), which command it runs, which parsers exist, and any known gaps (unimplemented or stubbed paths). Note `Dockerfile.scanners` contents.
5. Security: `app/security/secret_evidence.py`, what redaction exists today.
6. Lease and completion: `app/services/lease_renewer.py`, `app/services/scan_orchestrator.py`, the r2 client, how completion is reported to the API.
7. Tests: inventory of `tests/`, which gate on env vars (REDIS_URL and others), how scanner tests fake or run binaries, and what `test_redis_stream_recovery_integration.py` needs.
8. Versions: pinned scanner versions anywhere (pyproject, Dockerfile, docs), and which of trivy/gitleaks/semgrep/syft/grype/checkov/osv-scanner binaries are on PATH with their versions (`--version`).

ACCEPTANCE: report written to `/home/nochaserz/Documents/Coding Projects/scanforge/orchestrate/managed-beta/reports/exp-worker.md` with file pointers and one-line summaries, no large code dumps. Include the binary version table.

TIMEBOX: 40 minutes. FORBIDDEN: any edit, any write outside the report file. REPORT: 10-line summary plus the report path.
