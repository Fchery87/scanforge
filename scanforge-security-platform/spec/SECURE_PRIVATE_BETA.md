# Secure private beta specification

## Status

Approved for planning on 2026-08-19.

## Product position

ScanForge is an evidence-first repository security operations product for GitHub teams. It runs a defined set of security scanners, records scanner health, normalizes findings, and preserves the evidence used to change finding state.

The private beta tests that promise with real design partners. Scanner count is not the beta's success measure. Trustworthy evidence is.

## Problem

The current implementation can lose queue jobs, report a scan as complete after finding persistence fails, retain secret values, and mix worker authority across organizations. The GitHub trigger and pull-request feedback paths are also incomplete. These failures prevent ScanForge from safely processing customer repositories.

The beta must prove that ScanForge can process private GitHub repositories without losing findings, exposing credentials, mixing customer execution, or reporting false success.

## Why now

ScanForge already has the main repository, scan, scanner-health, finding, and triage concepts. Market research found a credible position around evidence quality and explicit finding lifecycle state. Adding more product breadth before the evidence path is safe would increase risk without proving that position.

## Beta cohort

The initial cohort contains three design-partner organizations. ScanForge may expand to five organizations only after the expansion gate passes.

The beta uses hands-on onboarding and manually approved organizations. Public self-service signup is out of scope.

## Primary users

- A security reviewer who needs reliable findings and scan-health evidence.
- An organization owner or administrator who connects GitHub and manages access.
- A developer who receives advisory pull-request feedback and fixes findings.
- A ScanForge operator who provisions, observes, disables, and replaces dedicated workers.

## User outcome

Each design partner can complete this workflow:

1. Install the ScanForge GitHub App.
2. Connect an approved repository.
3. Trigger manual, scheduled, push, and pull-request scans.
4. Run the scan in the organization's dedicated worker environment.
5. Persist redacted findings and scanner-health evidence exactly once.
6. Review findings, evidence, and incomplete scanner coverage.
7. Triage findings and receive an advisory GitHub Check.
8. Recover from worker, queue, API, scanner, and storage failures without losing the scan or reporting false success.

## Architecture

### Shared application components

The following components remain shared:

- The Next.js web application.
- The FastAPI service.
- PostgreSQL.
- The GitHub App and webhook receiver.
- The scan scheduler.
- Deployment monitoring and operator alerting.

Shared components coordinate scans and store product state. They do not execute scanner processes.

### Dedicated worker boundary

Each beta organization receives one dedicated worker host. The host runs one queue consumer and one scan at a time. It has a fixed `WORKER_ORGANIZATION_ID` and an organization-scoped worker credential.

The worker consumes only the organization's queue namespace. It cannot request execution context, clone credentials, artifact URLs, finding persistence, or scan-state changes for another organization.

The worker receives no database credentials and no object-storage account credentials.

### Scan containment

The dedicated worker host separates customers. A restricted scanner runtime separates each scan from the worker coordinator.

The coordinator performs authenticated clone, API calls, queue operations, normalization, and persistence. Scanner commands run in a disposable container with:

- A non-root user.
- A read-only source mount.
- A separate writable output directory.
- No worker credential or GitHub token.
- No Docker socket.
- No outbound network during scanner execution.
- Dropped Linux capabilities.
- CPU, memory, process, disk, and runtime limits.
- Cleanup after success, failure, cancellation, or timeout.

Scanner databases and rules are pinned in the scanner image. A trusted image build updates them. Scanner containers do not download updates while processing customer code.

### Queue contract

Each organization has one Redis Stream, one consumer group, and one dead-letter stream. The queue namespace includes the organization ID.

The API adds one message per scan. The message contains the scan ID. The scan ID is the idempotency key. The worker uses consumer-group pending entries for crash recovery and `XAUTOCLAIM` for stale jobs.

The worker acknowledges a message only after the API commits the completion transaction. Reclaim runs continuously in the worker loop. Recovery does not depend on a weekly maintenance task.

### Worker identity

The API stores one or more worker identities per organization. It stores only a hash of each credential. A verified credential produces a service principal with an organization ID, worker ID, status, and allowed capabilities.

Internal endpoints derive organization access from the service principal. They reject organization identifiers supplied as authority in request bodies.

Operators can rotate, disable, and inspect worker identities. Disabling an identity stops new clone, artifact, persistence, and state-change requests immediately.

### Repository credentials

The API constructs the canonical GitHub clone URL from the verified repository owner and name. It does not use an arbitrary stored clone URL for authenticated cloning.

Before issuing a short-lived installation token, the API confirms that:

- The repository belongs to the worker's organization.
- The organization has an active GitHub installation.
- The GitHub installation can access the repository.
- The requested scan belongs to the repository and organization.

The clone credential exists only in the coordinator process for the clone operation. Scanner containers never receive it.

### Secret evidence

Secret matches must not cross a durable or external boundary.

For a secret finding, ScanForge may store:

- The scanner and rule identifier.
- The secret type.
- The repository-relative file path.
- The start and end line.
- The commit identifier.
- A canonical finding fingerprint that does not contain the secret value.

ScanForge must not store the matched value, a reversible encoding, or a short unkeyed hash of the value in PostgreSQL, object storage, logs, notifications, metrics, audit records, or AI requests.

Raw Gitleaks output is not retained. Trivy secret output is sanitized before artifact upload. Object keys begin with `scan-artifacts/{organization_id}/{scan_id}/`. The storage lifecycle policy targets `scan-artifacts/`.

AI investigation remains disabled for the private beta. Re-enabling AI requires a separate review and a canary-secret test that covers every scan type.

### Atomic completion

Progress updates are advisory. They may report stages such as cloning or scanning.

Only the API completion operation may set a scan to `completed`. That operation commits these changes in one database transaction:

- Scanner-run results and health.
- Canonical findings.
- Idempotent finding instances.
- Finding references.
- The completion summary.
- Finding lifecycle evaluation.
- The final scan status.

If the transaction fails, the scan remains incomplete and the queue message remains pending. Repeating the operation with the same scan ID produces the same durable result.

Cancellation is terminal. A worker cannot change a canceled scan to running, failed, or completed.

### GitHub workflow

Manual, scheduled, push, and pull-request triggers call the same scan lifecycle service.

Pull-request scans record the pull-request number, base commit, and head commit. Diff calculation uses the recorded base and head. It does not infer the base from `HEAD~1`.

ScanForge publishes one GitHub Check per pull-request scan. The check reports:

- Scan status.
- Scanner failures and missing coverage.
- Finding counts by severity.
- The advisory policy result.
- A link to the ScanForge scan page.

The private beta check is advisory. Merge blocking remains out of scope until evidence completeness and policy behavior are proven with design partners.

## Access and audit requirements

- Viewer members cannot create, update, or delete schedules.
- Inactive users cannot authenticate.
- Beta JWT validation requires the configured issuer and audience.
- Every mutation writes an audit event with a verified actor.
- Request-local state carries the actor. Process-global mutable audit state is prohibited.
- Project audit queries return only events for that project.
- Internal worker mutations record the worker identity as the actor.

## Reliability requirements

- A process crash after queue claim does not lose the scan.
- A persistence failure does not produce `completed` status or queue acknowledgement.
- A repeated queue delivery does not duplicate a finding instance.
- A queue or API outage recovers without manual Redis key repair.
- Scanner failure remains distinct from orchestration failure.
- An incomplete scanner set cannot close a finding.
- Operators can stop one organization's worker without affecting another organization.
- The scheduler accepts only frequencies that it executes correctly.

## Operational requirements

The committed deployment configuration must create or document:

- The shared API and scheduler.
- A repeatable dedicated-worker host configuration.
- A pinned scanner image.
- Database migrations before application rollout.
- Health and readiness checks.
- Organization-scoped secrets.
- Queue, worker, persistence, scanner, and storage alerts.

The operator runbooks must cover:

- Provisioning and removing a beta organization.
- Worker credential rotation.
- Worker replacement.
- Organization kill switch activation.
- Dead-letter recovery.
- Database backup and restore.
- Object-storage retention verification.
- Incident response for exposed source code or credentials.

## Quality gates

### Gate 1: evidence integrity

- Persistence failure leaves a scan incomplete and retryable.
- Worker termination after claim results in automatic recovery.
- Replayed jobs do not duplicate durable evidence.
- Cancellation prevents later completion.
- The full API suite terminates and passes against PostgreSQL.

### Gate 2: secret safety and containment

- Canary secrets do not appear in PostgreSQL, object storage, logs, notifications, or external requests.
- A worker cannot access another organization's resources.
- A clone request cannot send GitHub credentials to an unapproved origin.
- Scanner containers run without credentials or outbound network.
- Resource-limit tests stop oversized or hostile fixtures.

### Gate 3: GitHub workflow

- Every trigger creates and enqueues one scan through `ScanLifecycleService`.
- Pull-request scans use the recorded base and head commits.
- ScanForge publishes and updates an advisory GitHub Check.
- Scanner-health failures appear in the check and the scan page.

### Gate 4: beta operations

- A clean staging environment deploys from committed configuration.
- Migrations apply to an empty PostgreSQL database and an upgraded staging copy.
- Backup and restore, worker replacement, credential rotation, dead-letter recovery, and kill-switch drills pass.
- Monitoring detects queue age, failed persistence, scanner failure, storage failure, and worker health.

## Success measures

The initial beta succeeds when:

- All three organizations complete onboarding and a first scan.
- At least 95 percent of scans start within five minutes under the beta load limit.
- No scan is reported complete without committed evidence.
- No confirmed secret value reaches a prohibited boundary.
- No worker accesses another organization's resource.
- All crash-recovery drills recover within ten minutes.
- Every production incident has an audit trail and an operator response record.
- Each partner uses finding triage for at least two weeks.

These measures are beta gates, not public service-level commitments.

## Expansion gate

ScanForge may expand from three to five organizations when:

- The initial cohort has two consecutive stable weeks.
- Every organization has completed onboarding and failure drills.
- Backup and restore have passed against current staging data.
- There is no unresolved credential-isolation or cross-tenant incident.
- There is no unresolved evidence-integrity incident.
- Operator workload remains within the documented support capacity.

## Out of scope

- Public self-service onboarding.
- More than five beta organizations.
- GitLab or Bitbucket.
- DAST, cloud posture, runtime security, and container-registry scanning.
- SAML and SCIM.
- Merge blocking.
- Automated code repair.
- AI investigation.
- Generic AI chat.
- Reachability analysis.
- Customer-hosted runners.
- A multi-tenant shared scanner worker.

Incomplete exports remain hidden during the beta. Building export generation is not required for this release.

## Post-beta product work

After the beta passes, the next competitive work is:

1. Add KEV and EPSS to the transparent risk score.
2. Add Jira or another work-management integration.
3. Add advisory, warn, and block policy modes.
4. Add deterministic dependency-fix pull requests.
5. Publish pricing, support terms, privacy terms, subprocessors, and trust evidence.

Do not start this work until the beta quality gates pass.

## References

- `CONTEXT.md`
- `docs/adr/ADR-002-canonical-finding-model.md`
- `docs/adr/ADR-003-scan-lifecycle-architecture-program.md`
- `docs/adr/ADR-004-finding-lifecycle-policy.md`
- `docs/adr/ADR-005-worker-pipeline-stages.md`
- `docs/adr/ADR-009-dedicated-workers-for-private-beta.md`
- `docs/plans/2026-08-19-secure-private-beta-implementation-plan.md`
