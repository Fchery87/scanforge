# apps/worker convention map (coordinator-persisted from explorer report 821f8e05)

1. Worker root in the worktree is `scanforge-managed-beta/scanforge-security-platform/apps/worker`. Runtime selection (`app/runtime/base.py`) uses `DockerScanRuntime` only when `APP_ENV=private-beta` (image must be digest-pinned, docker on PATH, hard RuntimeError otherwise, no silent fallback), else `LocalScanRuntime` with empty env.
2. Docker runtime (`app/runtime/docker.py`) runs scanners `--read-only --network=none --cap-drop ALL`, uid 65532, with pids/mem/cpu/tmpfs limits; timeout kills the CLI process group then force-kills the named container (30s budget, exit 124).
3. Main loop (`app/worker/main.py`) is asyncio, `WORKER_CONCURRENCY` (default 2) concurrent `process_single_job` tasks over an Upstash-REST Redis Streams queue (`queue:scans:{org}`, group `scanforge-workers`, XAUTOCLAIM reclaim, DLQ plus retry zset with Lua atomicity, bounded backoff on poll failures).
4. Pipeline (`app/services/scan_pipeline/`): execution (https-github-only shallow clone via allowlisted env plus GIT_CONFIG extraHeader; per-scanner runs reported to API; 1800s cap) → normalization (registry normalizers plus `sanitize_secret_finding`) → persistence (`POST /internal/scans/{id}/complete` with winning_attempt_id plus execution_revision).
5. Scanner gap: only trivy and gitleaks override `runtime_arguments()`/`parse_runtime_result()`. osv, semgrep, syft, checkov, grype would just run `--version` in contained docker mode. Contained scanning is incomplete for 5 of 7.
6. semgrep uses `--config auto`, which needs network, incompatible with `--network=none`. Gitleaks raw output is dropped entirely. Trivy output is sanitized before any boundary.
7. Security: `app/security/proc_env.py` env allowlist; `secret_evidence.py` redacts secret values and enforces tenant-scoped artifact keys; `redaction.py` contains a corrupted dead regex pattern (asterisks only).
8. Lease: `LeaseRenewer` heartbeats attempt_id/execution_revision every 30s; 409 raises LeaseLostError and the orchestrator cancels the pipeline, leaving the job pending; retries capped at 3, then DLQ plus Slack.
9. Tests: 25 files, all unit. Only `test_redis_stream_recovery_integration.py` needs native Redis via `REDIS_URL` (defaults 127.0.0.1:6379/15; fixtures must point it at 6399). Scanner tests fake binaries via monkeypatched `subprocess.run`.
10. Versions, host PATH vs Dockerfile.scanners pins: trivy 0.69.3 = 0.69.3; gitleaks 8.30.1 vs 8.30.0; osv-scanner 1.9.2 vs 2.3.3 (major divergence); semgrep 1.156.0 = 1.156.0; syft 1.42.3 = 1.42.3; grype 0.110.0 = 0.110.0; checkov host version uncaptured vs 3.2.513 pin.

## Facts the M04/M05 briefs must carry

- The plan's M05 regression target is confirmed real: gitleaks evidence dies between execution and normalization today.
- Five of seven scanners have no contained command or parser; M05 implements one adapter at a time against the pinned executable.
- semgrep offline needs a pinned rules pack, not `--config auto`, to honor the no-network runtime.
- osv-scanner pin (2.3.3) and host binary (1.9.2) disagree on major version; M05 must reconcile the pin before fixture runs.
- The corrupted regex in `redaction.py` is a standing defect to fix in the M05 redaction slice, regression-first.
- No silent local fallback exists in private-beta mode, which matches the plan; M04's fixture work proves the RuntimeError path and the containment flags rather than inventing a fallback.
