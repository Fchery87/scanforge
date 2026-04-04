# Scanner Pipeline

## Current Execution Model

1. A scan request creates a `scans` row with status `queued`.
2. The API enqueues a queue job with scan, organization, project, repository, branch, commit, and user context.
3. The worker dequeues the job and marks the scan `running`.
4. The worker requests an authenticated clone URL from the internal API.
5. The repository is cloned into a temporary directory.
6. The worker selects scanners by scan type.
7. Scanners run independently and create `scanner_runs` records.
8. Raw outputs and generated artifacts are uploaded to object storage.
9. Normalizers convert scanner-specific output into the canonical finding shape.
10. For diff scans, findings can be filtered to changed files.
11. The worker persists findings through internal API routes.
12. The scan summary is updated and notifications may be emitted.

## Scan Type To Scanner Mapping

- `scan.repo.full`: Trivy, Gitleaks, OSV, Semgrep, Syft, Checkov, Grype
- `scan.repo.diff`: Gitleaks, Semgrep, Checkov
- `scan.dependencies`: Trivy, OSV, Syft, Grype
- `scan.secrets`: Gitleaks

## Worker Responsibilities

- queue consumption
- retry tracking and dead-letter handling
- repository cloning
- scanner run creation and status updates
- artifact upload
- normalization
- finding persistence
- success and failure notifications

## API Responsibilities In The Pipeline

- create scan records
- authorize scan requests
- enqueue jobs
- issue authenticated clone information for workers
- accept scanner run and finding persistence callbacks
- serve artifact download redirects

## Current Gaps Observed In Review

- queue payload and worker test contracts are drifting
- validation coverage exists, but some worker tests and OAuth regression tests are currently failing
- scanner execution depends on external binaries and valid queue and storage credentials, so local runtime parity requires more than Docker services alone
