# Implement evidence-first private-beta readiness

**Status:** Not started

**Spec:** [Evidence-first readiness](../../spec/2026-09-13-evidence-first-readiness.md)

Use this plan to make scan results trustworthy for security reviewers and developers.
Do not treat this document as approval to deploy, onboard customers, or merge changes.
Keep AI disabled and pull-request feedback advisory throughout the beta.

## How to read this

One box is one unit of work. Each task names the evidence needed to finish it.
Check a box only when its evidence exists and identifies the tested revision.
Record the accepted commit SHA, command output, fixture, and result in the task table.
Use `git cat-file -t <sha>` to verify recorded commits after a rebase.
No task is complete merely because a file exists or an earlier review reported passing tests.

This is the active execution tracker for the readiness work. It replaces the execution order in the
[August beta plan](2026-08-19-secure-private-beta-implementation-plan.md), not its requirements.
The [approved beta specification](../../spec/SECURE_PRIVATE_BETA.md) and accepted ADRs remain authoritative.
The September spec remains proposed where it introduces new contract details.
Resolve conflicts in R03 before contract implementation. Do not silently widen beta scope.

Execution starts only after a separate implementation instruction. Use the installed Poteto Bug fix
playbook for reproduced defects and Feature playbook for new behavior. These playbooks are the execution playbooks. Deliver small reviewed PRs.
Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. This plan uses concrete live scenarios and performance receipts instead of an autonomous fleet.
No automatic `/goal`, heartbeat, fleet, Graphite stack, or merge program is armed by this document.
The operator retains approval of deployments, destructive drills, customer onboarding, and merges.

## Establish the baseline before editing

- [ ] R00. Record the Git root, branch, HEAD, tracked diff, and untracked files without reading secrets.
- [ ] Map existing private-beta changes to the tasks below. Adopt and test existing work rather than recreating it.
- [ ] Create a safe branch or worktree after recording how in-flight work will be preserved. Never reset or discard the dirty tree.
- [ ] Record the current test results. The prior review reported API 133 passed, worker 74 passed, lint passed, and web failure. The current R01 run passes the web suites through `make test`. These results are working-tree evidence until committed.
- [ ] Capture a disposable PostgreSQL, Redis Streams, MinIO, and Linux Docker fixture configuration without production credentials.

## Track tasks and dependencies

Use states `Not started`, `In progress`, `Done, unverified`, and `Done`.
`Done` requires a verified SHA and the unit, integration or live, and performance evidence specified below.
A missing credential or unavailable runtime is `Blocked` in the evidence column, never a pass.

| ID | Deliverable | Depends on | State | SHA | Required evidence |
| --- | --- | --- | --- | --- | --- |
| R00 | Preserve and reproduce the baseline | None | Done | d54f4e9 | `/tmp/scanforge-r00-baseline-2026-09-13.txt`; preserved before focused commit |
| R01 | Repair web test selection | R00 | Done | d54f4e9 | Node 75 passed; Vitest 3 passed; `make test` passed; `make lint` passed |
| R02 | Activate CI at the actual repository root | R01 | In progress | Pending | Local YAML/path validation passed; real PR run still required |
| R03 | Settle evidence-contract and transition policy | R02 | Not started | Pending | Decision table, fixtures, ADR disposition |
| R04 | Enforce API-owned atomic completion | R03 | Not started | Pending | PostgreSQL rollback, replay, concurrency, cancellation tests |
| R05 | Make disappearance and triage scope-safe | R04 | Not started | Pending | Comparable-scan matrix, transition tests, browser evidence |
| R06 | Close user and worker authorization gaps | R02 | Not started | Pending | Two-organization route and service tests, audit evidence |
| R07 | Enforce scanner containment and cleanup | R02 | Not started | Pending | Real Docker hostile-fixture and cleanup receipts |
| R08 | Prove secret and artifact safety | R04, R06, R07 | Not started | Pending | Canary scan, storage and egress inspection |
| R09 | Make queue failure and recovery observable | R04 | Not started | Pending | Real Streams crash recovery, alert and health receipts |
| R10 | Complete GitHub triggers and advisory Checks | R05, R06, R09 | Not started | Pending | Recorded base/head diff, replay-safe Check, staging GitHub flow |
| R11 | Repair browser contracts and triage experience | R05, R06, R10 | Not started | Pending | Contract tests, authenticated browser scenarios, keyboard review |
| R12 | Prove deployment and operational recovery | R08, R09, R10, R11 | Not started | Pending | Clean staging deployment, migrations, recovery drills |
| R13 | Close release gates and approve cohort rollout | R12 | Not started | Pending | Aggregate gate, independent review, operator acceptance |

### Divide ownership without conflicting writes

After R02, R03, R06, and R07 can be investigated independently.
R04 and R06 both touch internal API routes. Serialize those edits or explicitly assign the shared file to one owner.
R07 and R08 share scanner execution code. Finish R07 before integrating R08.
R04 and R09 share completion and acknowledgement behavior. Finish R04 before integrating R09.
R10 consumes the settled R05 lifecycle contract. R11 consumes the final API contracts.
One owner writes migrations at a time. Inspect the actual Alembic head before assigning a revision number.

## Restore executable release checks

### R01. Run all intended web tests

- [ ] Inspect `apps/web/package.json`, `vitest.config.ts`, and test imports. Convert `node:test` files to Vitest or declare a separate runner. Do not exclude failing tests to make the count green.
- [ ] Retain the proxy no-cookie-logging regression and add a test inventory check that catches silently omitted files.
- [ ] Run the web commands in Appendix A, then the full local gate. Record collected files and test totals.
- [ ] Build and start the production web artifact locally with test configuration. Verify sign-in entry and a representative component interaction. Save a screenshot and browser errors.
- [ ] Record runner and build duration before and after on the same host. Investigate a median regression above 20 percent across three runs.

### R02. Make CI enforce the real checkout

- [ ] Verify `git rev-parse --show-toplevel` and tracked workflow paths. Move workflow discovery to the actual root if necessary.
- [ ] Correct working directories, path filters, lockfile paths, generated-contract checks, dependency audits, and SBOM scope for the nested project.
- [ ] Trigger checks for workflow-only, shared-contract, infrastructure, API-only, and web-only changes. Add an always-present aggregate check that cannot pass when a required job fails or is unexpectedly skipped.
- [ ] Use deterministic installs. Fix audit commands against the actual dependency inputs instead of copying flags without a supported lock format.
- [ ] Run CI on a real non-production PR. Save the run URL and tested SHA. Verify required-check configuration or record its absence as a release blocker.
- [ ] Compare job duration against R00 with the same dependency cache state. Explain regressions above 20 percent rather than suppressing checks.

## Prove the evidence contract

### R03. Resolve architecture details before creating an ADR

- [ ] Read ADR-002, ADR-003, ADR-004, and ADR-009. Record which requirements are already accepted.
- [ ] Compare extending existing scan and scanner-run records with a versioned completion payload. Do not create a second evidence store by default.
- [ ] Define contract version negotiation, scanner-level provenance, payload limits, authoritative field ownership, and how the API derives summaries.
- [ ] Define comparability as a relationship between a finding's prior evidence and a new scanner run. Do not use one worker-supplied boolean for the whole repository.
- [ ] Define safe treatment of legacy scans with missing provenance. Use unknown or incomparable, not retroactive claims of a clean scan.
- [ ] Define ref and commit ancestry rules. Different commits must be comparable for remediation, but unrelated branches must not close each other's findings.
- [ ] Define rules and database freshness. Exact version equality forever would prevent useful rescans after updates. Unknown compatibility remains non-closing until a documented rule proves equivalence.
- [ ] Reconcile partial-health semantics. The proposed spec forbids partial-health closure. Preserve operational completion with explicit partial health, but require a fully validated closure policy. Any per-scanner exception requires an explicit spec decision.
- [ ] Define allowed source and target states, actor capabilities, required reasons, expiry behavior, fixed-promotion threshold, reappearance reset, and manual-resolution evidence.
- [ ] Reconcile canceled-message acknowledgement. The older plan acknowledges confirmed cancellation, while the newer contract says acknowledgement requires completion. Define the durable terminal cancellation record and authorized acknowledgement path without pretending cancellation is successful scan completion.
- [ ] Record a new ADR only if these choices add a settled decision beyond the existing ADRs. Otherwise link the existing decisions and document why another ADR is unnecessary. Do not reserve ADR-010 without checking the next available number.
- [ ] Verify decisions against empty results, unknown provenance, changed files, scanner updates, repeated delivery, and unrelated branches. Save the decision matrix for R04 and R05 tests.

### R04. Validate and commit completion atomically

- [ ] Extend `apps/api/app/schemas/scan_completion.py` and `services/scan_completion.py` using the R03 contract. Update worker persistence and generated web contracts together.
- [ ] Reject malformed, unknown, duplicate, or contradictory scanner results. Derive expected scanners from persisted scan context. Represent explicit failure and missing coverage separately from forged success.
- [ ] Derive seen fingerprints from accepted findings. Validate artifact ownership and bounded payload sizes at the API boundary.
- [ ] Keep scanner runs, findings, instances, references, lifecycle events, summary, and terminal status in one transaction. Remove alternative completion and disappearance mutation paths.
- [ ] Add PostgreSQL tests for failure at each write stage, concurrent completion, replay after commit response loss, conflicting replay policy, canceled scans, stale attempts, and no duplicate occurrences.
- [ ] Prove with a real worker that API failure prevents acknowledgement and retry converges on one durable result.
- [ ] Measure completion p95 at fixed payload sizes and concurrent requests. Record three baseline and candidate runs. Investigate a regression above 20 percent and all unbounded payload behavior.

### R05. Enforce comparable disappearance and real transitions

- [ ] Replace the primary-scanner-only predicate in `services/finding_lifecycle.py` and repository-wide diff behavior in `services/findings.py`.
- [ ] Keep disappearance disabled for diff scans until a scoped policy is explicitly accepted. Preserve findings in unchanged files.
- [ ] Write regression cases for ref, commit model, path filters, scanner version, rules version, database freshness, parser failure, empty output, skipped scanner, and absent provenance.
- [ ] Count distinct qualifying scan evidence, not delivery attempts. Reset consecutive absence evidence when a finding reappears. Test out-of-order scans and overlapping full and diff scans.
- [ ] Implement the R03 transition table and actor/evidence requirements. Retain existing FindingEvent history unless the ADR establishes a necessary replacement.
- [ ] Run the finding and completion suites against PostgreSQL. Demonstrate a full scan followed by two unrelated diff scans without closing an unchanged finding.
- [ ] Show state, reason, and evidence in the authenticated UI. Save before/after screenshots and a short video for operator review.
- [ ] Measure lifecycle evaluation time and query count at a fixed 10,000-finding fixture. Investigate p95 regressions above 20 percent and per-finding query growth.

## Close security and execution gaps

### R06. Enforce access inside services and worker routes

- [ ] Check notification recipient membership and export creation authorization inside their owning service boundaries.
- [ ] Cover every internal capability with two-organization tests for scan, clone, status, findings, notifications, and artifact access.
- [ ] Test disabled and rotated identities, inactive users, viewer schedule mutations, issuer and audience validation, and scheduler isolation.
- [ ] Prove request-local audit actors under concurrent requests. Test project-filtered audit results and worker mutation events.
- [ ] Verify canonical clone origin and GitHub installation access after repository rename, transfer, or installation removal.
- [ ] Run route and direct-service regressions. Drive negative requests against a disposable API and compare database rows and audit events before and after.
- [ ] Measure authorization p95 under a fixed request set. Investigate regressions above 20 percent and cross-request identity leakage.

### R07. Kill and clean scanner processes on every exit

- [ ] Use explicit container identity and cleanup in `apps/worker/app/runtime/docker.py`. Cover cancellation, timeout, daemon failure, and coordinator termination.
- [ ] Verify actual non-root, read-only, network, capability, PID, memory, CPU, output-size, and disk constraints. A host output mount alone does not impose a disk quota.
- [ ] Build the pinned image. Verify scanner binaries, rules, vulnerability databases, checksums or signatures, manifest freshness, and offline operation for all seven scanners.
- [ ] Run hostile fixtures for disk growth, oversized output, fork attempts, symlinks, network access, and timeout. Inspect Docker daemon state, not only command arguments.
- [ ] Run ten repeated timeout cycles. Require zero residual containers or growing temporary directories. Proposed cleanup budget is 30 seconds after the configured deadline, subject to recorded baseline review.

### R08. Prove secret safety through the real pipeline

- [ ] Run unique synthetic canaries through full, diff, dependencies, and secrets scans with the pinned scanner image. Reject short unkeyed hashes or value-derived previews as secret evidence.
- [ ] Inspect normalized findings, PostgreSQL, uploaded objects, logs, audit records, notifications, caches, and outbound requests for plaintext and reversible encodings.
- [ ] Verify raw Gitleaks output is absent, Trivy secret evidence is sanitized, and arbitrary metadata or error fields cannot reintroduce secret values.
- [ ] Keep AI disabled and prove the beta configuration rejects enablement. Confirm scanner containers have no credentials or Docker socket.
- [ ] Verify exact-key upload authorization, download isolation, artifact prefix, and configured retention in staging. Do not enable a deletion policy on customer data during a test.
- [ ] Run the secret tests plus a full worker/API/storage scan. Save sanitized receipts only. Fail on any canary exposure regardless of performance.
- [ ] Compare sanitize/upload duration at identical fixture sizes. Investigate regressions above 20 percent without removing safety checks.

### R09. Recover jobs and expose queue outages

- [ ] Separate empty, unavailable, unauthorized, and rate-limited queue outcomes in both client and worker behavior.
- [ ] Add bounded backoff, degraded readiness, recovery logging, queue-age metrics, and persistence/scanner/storage alerts. Keep process liveness independent of external health.
- [ ] Test real Streams claim, continuous reclaim, retry, dead-letter transfer, duplicate delivery, worker kill after claim, and commit-before-ack response loss.
- [ ] Verify stale claims cannot permit two workers to apply conflicting attempt results. Reconcile this with R04 attempt validation.
- [ ] Run native Redis tests and an Upstash REST-compatible staging test. Native Redis success alone does not prove REST command behavior.
- [ ] Measure recovery and alert delay. Require recovery within ten minutes under the beta fault fixture and no acknowledgement before committed evidence.

## Complete the beta user workflow

### R10. Publish reliable advisory GitHub Checks

- [ ] Route manual, scheduled, push, and pull-request triggers through `ScanLifecycleService`. Verify webhook signatures and replay safety.
- [ ] Persist and fetch exact base and head commits. Replace `HEAD~1` inference. Fail explicitly when either commit cannot be verified.
- [ ] Execute only supported schedule frequencies and reject unsupported custom expressions.
- [ ] Publish queued, running, completed, partial, failed, and canceled outcomes to one persisted Check identity per scan.
- [ ] Keep Check publication retryable after evidence commits. GitHub outage must not roll back evidence or cause duplicate Checks.
- [ ] Test counts, scanner gaps, policy result, links, retries, redaction, webhook replay, and base/head updates. Never configure advisory Checks as required merge gates.
- [ ] Use CI GitHub fixtures and one approved staging installation with a real pull request. Save Check URLs and compare displayed state with API evidence.
- [ ] Measure commit-to-Check latency. Propose a 60-second publication target after completion under normal staging conditions. Record failures separately from scan completion.

### R11. Make browser state and API failures explicit

- [ ] Audit the onboarding request and actual API routes before choosing a fix. Wire a real endpoint or remove the invalid request. Never show request failure as successful empty data.
- [ ] Replace unchecked critical-response casts with generated types and runtime boundary validation. Test 204, 401, 403, 429, 500, timeout, and malformed payloads.
- [ ] Keep request retries bounded and preserve user-entered state. Scope stored preferences by organization and user.
- [ ] Use one production finding drawer. Finish loading, error, empty, focus trap, Escape, focus restoration, keyboard, and screen-reader behavior.
- [ ] Keep incomplete exports hidden. Do not add an export generator as a prerequisite for this beta.
- [ ] Test onboarding, GitHub callback, partial scan, finding triage, notification navigation, and session expiry against a built web app.
- [ ] Save screenshots and video for operator review. Record browser errors and keyboard results, not just source-code assertions.
- [ ] Compare route-load and drawer-interaction p95 under a fixed seeded dataset and viewport. Investigate regressions above 20 percent across repeated runs.

## Prove the release candidate

### R12. Deploy clean staging and execute recovery drills

- [ ] Validate API, scheduler, and dedicated-worker configuration. Prove one scan per organization worker and absence of broad credentials.
- [ ] Apply migrations to an empty PostgreSQL database and an upgraded sanitized staging copy. Verify recovery from failed migrations before rollout.
- [ ] Implement or verify `make private-beta-gate`. Include lint, type checks, tests, migrations, build, dependency audits, real services, containment, and canaries. This target is planned, not assumed to exist.
- [ ] Run clean deployment, provisioning, backup/restore, replacement, rotation, kill switch, DLQ, queue, API, storage, persistence, scanner-timeout, retention, and incident-response drills.
- [ ] Require operator approval before deployment or destructive drills. Use disposable fixtures and approved staging targets only.
- [ ] Record alerts, failure-injection time, detection time, recovery time, data integrity, and sanitized evidence locations.
- [ ] Run the declared beta load fixture. Require at least 95 percent of scans to start within five minutes and fault recovery within ten minutes. Record the repository sizes, arrival rate, scanner image, and host capacity so the result is reproducible.

### R13. Review independently and approve controlled rollout

- [ ] Run the aggregate gate at the exact release SHA. An independent reviewer checks code, receipts, missing tests, and unresolved findings.
- [ ] Block rollout for evidence-integrity, tenant-isolation, secret-safety, cleanup, CI, or operational-proof failures.
- [ ] Prepare reusable sanitized acceptance templates. Store customer-specific receipts in approved restricted storage, not Git.
- [ ] Ask for operator approval before each design-partner onboarding. Confirm installation, worker identity, queue, artifact boundary, first scan, and recovery evidence.
- [ ] Review the approved cohort measures after two stable weeks of triage use. Confirm completed drills, incident records, current restore proof, and available operator support capacity. Expand from three to five only with explicit approval and no unresolved integrity or isolation incident.
- [ ] Keep public onboarding, AI, merge blocking, EPSS/KEV, Jira, generic imports, and automated fixes outside these PRs.

## Close the plan

- [ ] Verify each completed task SHA and evidence link. Record any remaining blocked requirement explicitly.
- [ ] Promote only settled new decisions into ADRs and permanent specs. Keep this plan from becoming a second product specification.
- [ ] Update the roadmap after acceptance. Retire this task tracker when its work is landed and durable documents preserve the outcome.

## Appendix A. Verification commands and evidence

Run commands from `scanforge-security-platform`, except Git root discovery.
Do not source a production `.env` for tests. R00 must provide isolated test configuration.

```text
git rev-parse --show-toplevel
git status --short
make lint
make test
make web-build
cd apps/web && npm test
cd apps/web && npx tsc --noEmit
cd apps/api && .venv/bin/python -m pytest tests -q
cd apps/api && .venv/bin/mypy app
cd apps/worker && .venv/bin/python -m pytest tests -q
```

Existing focused starting points include API `test_scan_lifecycle.py`, `test_finding_lifecycle_policy.py`,
`test_findings_scanner_integration.py`, `test_worker_identity_auth.py`, `test_route_integration_authorization.py`,
and worker `test_scan_orchestrator.py`, `test_docker_runtime.py`, `test_secret_boundaries.py`,
`test_queue_client.py`, and `test_redis_stream_recovery_integration.py`.
Add missing cases and dedicated completion, GitHub Check, migration, and browser tests as needed.
Do not infer real Docker or PostgreSQL coverage from a test filename. The inspected hostile-runtime tests mock execution, and the native Redis integration can skip when unavailable. Required release scenarios must execute, not skip.

For each task, save a receipt with task ID, SHA, environment/image versions, commands, exit codes,
fixture IDs, expected and observed results, timing samples, and sanitized artifact links.
Use structured API/database/container receipts for backend cases and screenshots/video for UI cases.
Performance thresholds above are proposed regression budgets, not measured baselines or public SLAs.
No production data or secrets may appear in receipts.

## Appendix B. Resolve overlap and architecture questions

| Earlier August task | Follow-up owner |
| --- | --- |
| 1. Test and dependency baseline | R00, R01, R02 |
| 2. Worker identities | R06 |
| 3. Organization Streams | R09 |
| 4. Atomic completion | R03, R04, R05 |
| 5. Terminal cancellation | R04, R07, R09 |
| 6. Secret boundaries | R08 |
| 7. Verified clone origin | R06, R08 |
| 8. Scanner containers | R07 |
| 9. Trigger parity | R10 |
| 10. GitHub Checks | R10 |
| 11. Access, audit, browser boundaries | R06, R11 |
| 12. Deployment | R12 |
| 13. Real integration gates | R04 through R12 |
| 14. Cohort acceptance | R13 |

ADR-003 already assigns lifecycle ownership. ADR-004 already requires comparable evidence.
ADR-009 already assigns worker isolation and acknowledgement invariants.
R03 settles only the additional versioning, compatibility, replay, and transition details.
Do not create an accepted ADR merely to repeat the September review.

The September spec lists GitHub work under post-gate capabilities, but the approved beta specification
requires advisory Checks before beta acceptance. R10 treats that requirement as a beta prerequisite.
SARIF, SBOM portability, EPSS/KEV, external tickets, and enterprise capabilities remain later planning topics.
The spec's temporary market-research path is not durable evidence. Before implementing market-derived
requirements, preserve dated first-party citations in a repository research document.

## Appendix C. Planning limits and unproven behavior

This task produced documentation only. No runtime prototypes, staging drills, new CI runs, or application fixes were performed.
R00 reproduces the review observations. R03 settles architectural details before writing contract logic.

Keel is not configured in this repository. Its plan lifecycle validator is unavailable.
The installed Poteto multi-phase checker assumes an armed autonomous fleet with ten named-model live lanes per PR.
That execution format is not authorized or configured here. This plan instead names concrete live scenarios and ownership boundaries.
Do not substitute fictitious model availability, screenshots, timers, or receipts to satisfy a template.
Use native agent delegation when implementation is authorized. Review UI evidence with the operator before merging UI changes.

## Appendix D. Read before editing

- [Readiness spec](../../spec/2026-09-13-evidence-first-readiness.md).
- [Approved private-beta spec](../../spec/SECURE_PRIVATE_BETA.md).
- [Domain glossary](../../CONTEXT.md).
- [Canonical finding ADR](../adr/ADR-002-canonical-finding-model.md).
- [Scan lifecycle ADR](../adr/ADR-003-scan-lifecycle-architecture-program.md).
- [Finding lifecycle ADR](../adr/ADR-004-finding-lifecycle-policy.md).
- [Worker isolation ADR](../adr/ADR-009-dedicated-workers-for-private-beta.md).
- [Operator runbooks](../runbooks/).
- [Earlier beta plan](2026-08-19-secure-private-beta-implementation-plan.md).
