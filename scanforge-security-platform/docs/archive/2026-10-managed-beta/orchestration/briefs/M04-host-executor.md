# M04 — Host executor and bounded workspace lifecycle

Track: worker. Depends on: M03 (contract authority) landed on the integration branch. Serialized after M05's parent within the worker track. Status: brief ready; spawn gated on M03.

## GOAL

A supervised host coordinator with a fixed organization identity, a controlled workspace root, bounded output, explicit cancellation handles, and contained customer execution required in customer-facing environments, with deployment artifacts that provision such a host reproducibly.

## SCOPE

Work in `/home/nochaserz/Documents/Coding Projects/scanforge-managed-beta/scanforge-security-platform` on the integration branch at its current head.

- Modify: `apps/worker/app/runtime/base.py`, `docker.py`, `containment.py`, `models.py`, `apps/worker/app/worker/main.py`, `apps/worker/app/services/scan_pipeline/execution.py`, worker deployment templates, `render.yaml`.
- Create: `infra/worker/scanforge-worker.service` (systemd unit, supervised, fixed org identity via env), `scripts/provision_worker_host.sh` (idempotent host provisioning: user, workspace root, ownership, runtime check), `apps/worker/tests/test_host_executor_integration.py`.
- Tests: extend the existing `test_docker_runtime.py` and `test_runtime_containment.py`.

## CONTEXT

- Plan authority: task M04 in the managed-beta plan; ADR-011 (`ADR-011-beta-executor-and-github-ingress.md`) in the shared tree docs/adr/, read-only.
- Convention map: `orchestrate/managed-beta/reports/exp-worker.md`. Key facts: runtime selection already refuses to run DockerScanRuntime without a digest-pinned image and docker on PATH (no silent fallback); the docker runtime already sets read-only, no-network, cap-drop, uid 65532, pids/mem/cpu/tmpfs limits; timeout kills the process group then force-kills the container.
- This host has NO docker and NO sudo (standing gate `docker-runtime`). Container-inspection acceptance items are recorded `verifier-blocked` with the gate named; everything else must actually run here.

## ACCEPTANCE

1. Regression-first repro fixtures for: missing git runtime, inaccessible uid/mount paths, local fallback reachable in a production environment (must be impossible), and unbounded output collection. Each reproduces before the fix, in `tests/test_docker_runtime.py` or `test_runtime_containment.py`.
2. A supervised host coordinator path exists: fixed org identity, controlled workspace root, one scan, local runtime, with source and output mount ownership fixed per tenant and never broadened.
3. Customer-facing environments require contained execution: `APP_ENV=private-beta` with docker absent fails hard with a documented error, proven by test. Local runtime remains for dev only.
4. Bounded stdout/stderr streaming with quotas and workspace quotas enforced in the execution path; explicit cancellation handles exposed to the orchestrator for process and container.
5. `infra/worker/scanforge-worker.service` and `scripts/provision_worker_host.sh` exist, are idempotent, and carry no credential literals (standing order 13); the script fails loudly when docker is missing in private-beta mode.
6. Container-inspection items (no scanner credentials/network/socket inside the container, stopped descendants on timeout/cancel) land as env-gated integration tests that run when docker exists; here they execute their gate and record `verifier-blocked: docker-runtime`.
7. Focused suites green locally; commits split per invariant (repro+fix per slice), enumerated paths only, SHAs via rev-parse.

## VERIFY

- `cd apps/worker && .venv/bin/python -m pytest tests/test_docker_runtime.py tests/test_runtime_containment.py -q` locally green.
- `.venv/bin/python -m pytest tests/test_host_executor_integration.py -q` with the local-runtime fixtures green; docker-gated cases recorded blocked with the gate id in the report.
- `bash -n scripts/provision_worker_host.sh` and `systemd-analyze verify infra/worker/scanforge-worker.service` (or record the verification binary's absence honestly).
- `git show --stat` per commit.

## TIMEBOX

2.5 hours. FORBIDDEN: silent local fallback in private-beta, broadened mount permissions, credential literals, docker or sudo attempts, edits outside enumerated paths, more than one writer on worker runtime files.

## REPORT

Status, branch, per-commit SHAs, local-suite outputs, the exact `verifier-blocked` list with gate ids, provisioning script dry-run evidence, deviations, follow-ups.
