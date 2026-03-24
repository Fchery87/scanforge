# Scanner Pipeline

## Step 1
Receive a scan request and create a `scans` row with status `queued`.

## Step 2
Worker claims the job and fetches the target repository snapshot.

## Step 3
Detect repository characteristics:
- language
- package managers
- lockfiles
- docker files
- infrastructure files

## Step 4
Run applicable scanner adapters:
- Trivy
- Gitleaks
- OSV-Scanner
- later: Syft, Grype, Checkov, Semgrep

## Step 5
Upload raw outputs to R2.

## Step 6
Normalize tool outputs into the canonical finding schema.

## Step 7
Update findings, finding instances, scanner runs, and scan summaries.

## Step 8
Trigger notifications and recalculate project score summaries.
