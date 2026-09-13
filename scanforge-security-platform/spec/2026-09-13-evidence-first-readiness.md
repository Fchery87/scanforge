# Evidence-first repository security operations readiness

**Status:** Proposed

**Date:** 2026-09-13

**Scope:** Private-beta hardening and the product direction that follows it.

**Implementation plan:** [Evidence-first readiness plan](../docs/plans/2026-09-13-evidence-first-readiness-plan.md).

The plan tracks execution and reconciles open contract decisions with existing ADRs. Creating the plan does not change this spec to Accepted.

## Problem

ScanForge has the right product shape for a GitHub-first repository security operations tool. It connects repositories, runs existing scanners, normalizes results, and gives security teams one place to review findings.

The product is not ready for public launch. The main risk is not missing scanner coverage. The main risk is false confidence. A partial, failed, or non-comparable scan must not make a finding appear fixed. A worker must not write across organizations. A timeout must not leave scanner processes running. A queue outage must not look like an idle worker. A release gate must test the real web, API, and worker paths.

The current private-beta design addresses many of these risks, but the implementation and operational proof do not yet satisfy every stated invariant.

## Product decision

ScanForge will position itself as a GitHub-first evidence and triage system for teams that already use multiple repository security scanners.

ScanForge will own the decision record around scanner output. It will not compete with broad AppSec suites by replacing every detector. It will preserve provenance, normalize results, show scanner health, support human triage, and publish useful advisory feedback in GitHub workflows.

The private beta will remain limited to three design partners and may expand to five only after the gates in this spec pass.

Public self-service onboarding, merge blocking, additional SCM providers, generic AI chat, automated repair, DAST, cloud posture, and runtime security remain out of scope for this phase.

## Data shape

The core readiness model is a versioned `ScanEvidenceContract` attached to every completed scan.

A `ScanEvidenceContract` contains:

- `scan_id`
- `organization_id`
- `project_id`
- `repository_id`
- `repository_owner`
- `repository_name`
- `ref`
- `commit_sha`
- `base_commit_sha` when the scan compares revisions
- `scan_type`
- `coverage_scope`
- `changed_files` when the scan is a diff scan
- `expected_scanners`
- `scanner_runs`
- `scanner_version`
- `rules_or_database_version`
- `parser_version`
- `completed_scanners`
- `failed_scanners`
- `missing_scanners`
- `coverage_complete`
- `coverage_comparable`
- `seen_fingerprints`
- `artifact_references`
- `started_at`
- `completed_at`

Each `scanner_run` records the scanner name, status, exit code, duration, version, rules or database version, scope, artifact references, and sanitized error data.

Each canonical finding retains its scanner identity, rule or advisory identifier, stable fingerprint, repository location, commit, package identity when applicable, external aliases, scan ID, and evidence references.

Finding state transitions use a separate `FindingTransition` record with the source state, destination state, actor, reason, evidence reference, review or expiry date, transition policy version, and event time.

This structure keeps scan evidence, finding identity, and user decisions separate. It prevents a summary field or a current risk score from becoming the only record of why a finding changed.

## Invariants

### Scan completion

- The API owns final completion.
- The API loads expected scanner data from authoritative scan state.
- The API rejects unknown or duplicate scanner names.
- The API records missing and failed scanners.
- A worker-provided summary cannot override server-derived execution facts.
- Persistence failure leaves the scan incomplete and retryable.
- Completion is idempotent for the scan ID.
- Cancellation is terminal.
- Queue acknowledgement occurs only after the completion transaction commits.

A scan may have an operational terminal status with partial scanner health only when the API labels that condition explicitly. Partial health must never authorize finding closure.

### Finding disappearance

- A diff scan cannot perform repository-wide disappearance evaluation.
- A finding can become `not_observed` only after a relevant scanner completed with comparable coverage.
- Comparability includes repository, ref, commit model, scan type, path scope, changed-file scope, scanner version, rules or database version, and relevant configuration.
- A finding can become `fixed` only after the configured evidence threshold passes.
- User actions and system transitions use separate policy paths.
- Every transition records an actor or a named system actor.
- Accepted risk and suppressions require a reason and review or expiry policy.

### Organization isolation

- The API derives worker organization access from the verified worker identity.
- Request-body organization IDs cannot broaden authority.
- Internal notification recipients belong to the worker organization.
- Clone credentials can access only the approved repository.
- Artifact keys include the organization and scan identity.
- Workers receive no database or object-storage account credentials.
- Scanner containers receive no worker, GitHub, database, or storage credentials.
- Disabling a worker identity blocks its next internal request.

### Scanner containment

- Scanner containers run as a non-root user.
- Source mounts are read-only.
- Output mounts are separate and bounded.
- Scanner network access is disabled.
- CPU, memory, process, disk, and runtime limits are enforced.
- Timeout and cancellation kill the container and clean its resources.
- Pinned image and scanner metadata are recorded with the scan.
- Scanner output is sanitized before durable storage.
- Secret values never enter the database, artifacts, logs, notifications, metrics, caches, or AI requests.

### Queue operations

- Empty queue and transport failure are different outcomes.
- Queue authentication, rate-limit, and network failures enter a degraded worker state.
- Reclaimed messages preserve the scan ID as the idempotency key.
- A pending message is acknowledged only after successful completion.
- Stale pending messages are reclaimed continuously.
- Queue age and oldest pending message are observable.

## Required implementation work

### Gate 1. Evidence integrity

1. Make finding disappearance scope-aware.
2. Disable repository-wide disappearance handling for diff scans.
3. Enforce the expected scanner set in the API completion transaction.
4. Derive scanner health from scanner-run records instead of trusting summary JSON.
5. Add PostgreSQL integration tests for rollback, replay, cancellation, partial health, and duplicate delivery.
6. Add tests proving that a persistence failure leaves the scan retryable.
7. Add tests proving that a diff scan cannot close a finding in an unchanged file.
8. Add tests proving that a non-comparable scanner version or rules version cannot close a finding.

### Gate 2. Organization and secret safety

1. Check organization membership for internal notification recipients.
2. Test every internal worker mutation across two organizations.
3. Test disabled and rotated worker identities.
4. Test clone-origin validation, repository transfer, and repository rename behavior.
5. Give scanner containers explicit IDs and kill them on timeout or cancellation.
6. Add hostile runtime fixtures that verify process, mount, output, and resource cleanup.
7. Run canary-secret fixtures through every scanner and inspect all prohibited boundaries.
8. Verify that artifact paths and download authorization cannot cross organizations.

### Gate 3. Web and release validation

1. Convert Node test-runner files to Vitest or exclude them from Vitest and run them in a separate command.
2. Make the root test command pass with the intended web, API, and worker suites.
3. Confirm the GitHub repository root and place `.github/workflows/ci.yml` under that root.
4. Use `npm ci` for reproducible deployment installation.
5. Remove unsafe `any` and unchecked casts from findings, onboarding, GitHub, notifications, exports, and scan paths.
6. Show actionable onboarding and API error states with retry behavior.
7. Finish finding-drawer dialog focus, keyboard, loading, and error behavior.
8. Build the web app in CI and run the built application on the release candidate.

### Gate 4. Beta operations

Run and record these drills in a clean staging environment:

- Database backup and restore.
- Worker replacement.
- Worker credential rotation.
- Organization kill switch.
- Dead-letter recovery.
- Queue outage recovery.
- API outage recovery.
- Storage outage recovery.
- Persistence failure recovery.
- Scanner timeout recovery.

Each drill records the injected failure, expected result, observed result, recovery time, logs, scan IDs, and follow-up work.

## Product capabilities after the gates

### Portable evidence

Support SARIF import and export for code findings.

Support CycloneDX storage and export for software bills of materials. Add SPDX support when customer demand requires it.

Preserve tool name, tool version, parser version, rule ID, advisory aliases, repository, commit, workflow run, path, line, package URL, artifact reference, and timestamp.

### Explainable prioritization

Extend the current transparent score with dated inputs:

1. EPSS score and percentile.
2. Known exploited vulnerability status.
3. Direct or transitive dependency status.
4. Dependency path.
5. Fix availability.
6. Repository ownership and importance.
7. Internet exposure when the product can prove the signal.
8. Reachability only after the product can explain the result.

Historical inputs remain attached to the decision that used them. New daily values do not rewrite prior evidence.

### GitHub workflow

Complete the GitHub-first workflow before adding another SCM provider:

- Repository synchronization.
- Push-triggered scans.
- Pull-request scans with recorded base and head commits.
- One advisory GitHub Check per scan.
- Retry updates to the same Check.
- Scanner failures and missing coverage in the Check.
- Policy result in the Check.
- Links to the exact ScanForge evidence.
- Actionable changed findings only.
- Duplicate-comment prevention.

Merge blocking remains deferred until design partners confirm that scanner health, deduplication, policy evaluation, and lifecycle behavior are trustworthy.

### Defensible triage

Implement a real transition table. Require reasons, actors, evidence, and review dates where the state requires them.

Add assignment, ownership, decision notes, and audited bulk actions.

Treat external issue creation as a projection of ScanForge state. Do not make Jira, GitHub Issues, or another external tracker the source of truth.

## Market and standards fit

GitHub already offers native code scanning, secret scanning, dependency alerts, SARIF integration, dependency review, SBOM functions, and merge protection. ScanForge must complement these capabilities.

Snyk and Aikido set expectations for broad scanning, prioritization, integrations, and remediation. Endor Labs sets expectations for software supply-chain analysis and agent workflows. DefectDojo and Dependency-Track validate the need for aggregation, SBOM analysis, and policy evaluation.

ScanForge should differentiate through evidence quality, scanner portability, GitHub context, explicit triage reasons, and low-noise advisory feedback.

Use OWASP ASVS mappings as versioned references. Do not claim that scanner output proves application conformance.

Map evidence to NIST SSDF practices and tasks where customers need audit reporting.

Use FIRST EPSS as one dated prioritization input. Do not present EPSS as evidence that exploitation occurred.

## Success measures

The private beta succeeds when:

- Three design partners complete onboarding and a first scan.
- At least 95 percent of scans start within five minutes under the beta load limit.
- No scan is reported complete without committed evidence.
- No confirmed secret value reaches a prohibited boundary.
- No worker accesses another organization's resource.
- Crash-recovery drills recover within ten minutes.
- Every production incident has an audit trail and response record.
- Each design partner uses finding triage for at least two weeks.

These are beta gates, not public service-level commitments.

## Out of scope for this spec

- Public self-service signup.
- GitLab or Bitbucket.
- DAST.
- Cloud posture.
- Runtime security.
- Container-registry scanning.
- SAML and SCIM.
- Merge blocking.
- Automated code repair.
- Generic AI chat.
- AI investigation during the private beta.
- Customer-hosted runners.
- A shared scanner worker for public multi-tenant use.

## Deletion inventory

The following approaches become obsolete as this spec is implemented:

- Repository-wide finding disappearance handling for diff scans in `apps/api/app/services/findings.py`.
- Primary-scanner-only disappearance authorization in `apps/api/app/services/finding_lifecycle.py`.
- Any completion path that trusts worker-supplied summary fields instead of server-derived scanner execution data.
- Any internal notification path that treats a caller-supplied user ID as sufficient organization authorization.
- Any timeout path that returns without terminating and cleaning the scanner container.
- Any queue path that treats transport failure as an empty poll.
- The nested CI workflow location if the actual GitHub repository root is outside `scanforge-security-platform`.
- Any duplicate or placeholder finding-drawer implementation that is not the owned production component.

No existing scanner adapter, canonical finding model, or approved private-beta boundary is removed by this spec.

## Verification plan

The implementation is complete for private-beta readiness only when all four gates pass in a clean staging environment.

The minimum command gate is:

```text
make lint
make test
make web-build
```

The API and worker suites must run against the supported database and queue contracts. The web suite must use one declared test-runner convention. CI must run from the actual GitHub repository root.

The failure drills and canary-secret tests are required evidence. A passing unit-test suite alone is not sufficient.

## Source documents

- `spec/SECURE_PRIVATE_BETA.md`
- `docs/adr/ADR-002-canonical-finding-model.md`
- `docs/adr/ADR-003-scan-lifecycle-architecture-program.md`
- `docs/adr/ADR-004-finding-lifecycle-policy.md`
- `docs/adr/ADR-009-dedicated-workers-for-private-beta.md`
- `CONTEXT.md`
- `docs/SYSTEM_OVERVIEW.md`
- `/tmp/scanforge-market-review.md`, the dated market research report from September 13, 2026
