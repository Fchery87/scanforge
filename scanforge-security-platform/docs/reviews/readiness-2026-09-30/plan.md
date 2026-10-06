# Private-beta implementation verification

This run implements the remaining beta requirements against the existing working tree. It preserves the pre-existing tracked diff and untracked source under `/tmp/scanforge-readiness-20260930`. The September readiness plan and approved beta specification define release scope.

## Completion criteria

The API, worker, and web gates pass. Each repaired behavior has a regression test. Live PostgreSQL, Docker, Redis REST, browser, GitHub, and staging evidence must execute before release approval. Missing infrastructure is a blocked release check, not a pass.

## Work sequence

1. Preserve baseline and reproduce available checks.
2. Repair all contained scanner adapters and artifact lifetime.
3. Enforce runtime cleanup, bounded output, and deployment prerequisites.
4. Close service and schedule authorization gaps.
5. Complete evidence validation and lifecycle transitions.
6. Complete GitHub trigger queueing, exact diff context, and advisory Checks.
7. Repair browser onboarding, response validation, drawer behavior, and hidden exports.
8. Distinguish queue outages and enforce bounded recovery.
9. Add executable beta gates and update task evidence.
10. Review the changes and run the combined checks.

## Throughput checkpoint

- Blocking first steps. Preserve the dirty tree and capture test baselines before edits.
- Independent workstreams. Scanner adapters, runtime infrastructure, and API service access have separate owners.
- Shared mutable state. One owner edits each file. API route, schema, and generated-contract work runs sequentially.
- Smallest safe decomposition. Keep each dependency chain with one owner and verify before the next dependent unit.

## Environment limits

Docker is absent at baseline. Staging access and production deployment are not part of this local run. No release claim can rely solely on mocked execution.
