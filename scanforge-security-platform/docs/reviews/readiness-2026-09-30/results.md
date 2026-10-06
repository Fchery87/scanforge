# Private-beta implementation results

Implementation is on `codex/private-beta-readiness-20260930`. The preserved starting commit is `f008a50`. These results describe an uncommitted working tree, including adopted pre-existing work. They do not approve release, deployment, or customer onboarding.

## Implemented behavior

- All seven scanner adapters execute report-producing contained commands. Scan-owned output survives normalization and upload. Failed uploads prevent completion and acknowledgement.
- Docker execution uses quota-limited temporary output, bounded export, explicit container removal, cancellation supervision, and unsafe-file rejection. Semgrep builds filter and validate a rules-only bundle.
- Completion validates bounded versioned evidence, artifact ownership, current attempts, actual repository commits, and server-owned lifecycle metadata. Progress endpoints cannot alter terminal evidence or persist findings outside atomic completion.
- Execution claims issue attempts separately from read-only status polls. Completed receipt-backed redeliveries acknowledge without rescanning. Git checkout and diff use recorded commits. Cancellation terminates Git processes before workspace removal.
- Disappearance compares per-finding scanner provenance and recorded branch evidence. Unknown or changed provenance cannot close a finding. Human dispositions require reasons and explicit reopening.
- Direct notification, export, and schedule services enforce active membership and roles. Supported schedules recalculate due times when edited.
- GitHub push and PR events preserve exact context. Neutral advisory Checks persist pending publication and retry through the scheduler. SLA evaluation uses stored overdue findings.
- Web requests validate response schemas. Onboarding derives real resources and exposes failures. The production drawer supports keyboard access, supported workflow states, stale-selection protection, and retry. Beta export generation is hidden.
- Queue commands expose dependency failures. Enqueue deduplication and stream insertion are atomic. Lease renewal verifies ownership. Dedicated beta workers enforce one active scan and publish readiness plus waiting-work age.
- Python constraints and web lockfiles pin audited dependencies. Render configuration defines the shared API and API-only scheduler. Organization scanners use dedicated Docker hosts.
- `make private-beta-gate` rejects missing live evidence, stale generated contracts, failed checks, and uncommitted release source. Local mode reports its narrower scope explicitly.

## Verification

The [local aggregate gate](evidence/local-gate-report.json) passed all 16 enabled checks. It returned success in local mode and recorded `release_ready=false`. The API passed 232 tests with two native PostgreSQL opt-in skips. Web passed 75 Node tests and 33 component tests, type checking, lint, and the production build. All three dependency audits found no known vulnerabilities.

The aggregate worker checkpoint passed 191 tests. Final worker-only review corrections then passed [192 tests](evidence/worker-final-review.log), with four live Docker skips. Those corrections capture each scan's runtime for delayed thread calls and include contained command arguments in configuration provenance. Worker lint also passed after those changes. Generated API schema and browser types match. Native PostgreSQL and Redis each passed two integration tests in separate processes.

Native PostgreSQL migrations reached the single `0021_github_scan_context` head. Concurrent completion, response-loss replay, conflicting replay, and rollback were exercised in a separate process. Native Redis exercised claim, reclaim, owner-checked heartbeat, acknowledgement, and atomic replay-safe API enqueue. This does not prove the hosted REST transport.

The independent review reproduced and corrected self-superseding execution polls, progress authority bypasses, lost artifact links, forged absence history, cancellation-before-launch races, invalid Semgrep configuration files, unsafe download keys, and inherited Git environment mutation. Review evidence and command logs are under `/tmp/scanforge-readiness-20260930`.

The [production browser observations](browser/observations.json) confirm invitation text, no signup link, signup page HTTP 404, and local signup forwarding HTTP 403. Authenticated flows remain unverified because the local identity-provider cookie secret is absent. The production preview remains available on port 3011.

A real local Boto3 signing check confirmed the conditional header is signed. This verifies signature construction, not storage enforcement. Disposable PostgreSQL and Redis fixtures were stopped after verification; their test configuration and logs remain under `/tmp/scanforge-readiness-20260930`.

## Remaining release evidence

Docker is not installed on this host. Image builds, all-seven-scanner execution against the real image, hostile Docker fixtures, and cleanup cycles remain unverified. Staging deployment, actual R2 conditional writes, hosted Redis REST recovery, live GitHub events and Checks, authenticated browser flows, recovery drills, monitoring delivery, identity-provider signup restrictions, and beta-load timing remain unverified. The active readiness tracker keeps these tasks `Done, unverified` or `In progress` and leaves accepted SHAs pending.

Artifact PUT signatures require create-only writes using R2's documented [conditional PutObject support](https://developers.cloudflare.com/r2/api/s3/api/). That documentation establishes API compatibility; a real storage receipt is still required. Artifact filenames include execution attempts so retries cannot overwrite earlier evidence.

## Decisions

Model the Domain shaped attempt identities, lifecycle transitions, and provenance snapshots. Separate Before Serializing Shared State assigned one file owner per workstream. Prove It Works required native PostgreSQL, Redis, and real Git fixtures, and kept unavailable Docker and staging checks unverified. Sequence Work into Verifiable Units kept fixes paired with focused checks before the aggregate gate.
