# ScanForge domain glossary

Domain terms for repository security operations. Accepted decisions live in [docs/adr](docs/adr/); the current execution plan is the [managed-beta implementation plan](docs/plans/2026-10-16-managed-beta-implementation-plan.md). Definitions describe domain meaning, not verified implementation status.

### Managed security operations beta

An invitation-only release for three to five organizations whose security reviewers use centralized repository scanning and finding triage, with onboarding managed by ScanForge operators.

### Release evidence

Recorded observations that demonstrate a release candidate satisfies its acceptance criteria in its intended operating environment.

### Partial scanner coverage

A scan outcome in which some valid analysis exists but one or more expected scanners lack a successful, valid result. Findings from valid analysis remain observations; missing coverage provides no evidence of absence.

### Redacted secret evidence

The detector identity, classification, verified repository revision, and location of a detected secret, with its value and sensitive matched content excluded.

### Branch generation

A continuous history of one repository branch whose revisions have verified ancestry. A recreated branch or unverified continuity begins a new generation; evidence from different generations cannot establish remediation by absence.

### Qualifying absence

An observation that a previously detected finding is absent under full, healthy, comparable scanner coverage at a verified revision within the relevant branch generation.

### Scan dispatch obligation

A durable obligation to deliver an accepted scan request for execution. An accepted request awaiting dispatch has not yet begun scanning.

### Cleanup pending

A scan condition in which a terminal decision exists but removal of its execution processes, containers, source, or temporary outputs has not yet been confirmed.

### Finalized artifact

An immutable, sanitized evidence object associated with a specific organization, scan, execution attempt, and scanner.

### Scanner provenance

The verified identity and freshness of the scanner, parser, rules, and databases responsible for an observation.

### Unresolved exposure

Findings that remain open, under review, awaiting remediation, or not yet proven fixed. Accepted risk is separately acknowledged exposure; duplicates contribute through their canonical target.

### Legacy unverified evidence

Historical evidence or conclusions whose provenance or decision authority cannot be established. Their existence is preserved without granting them verified remediation credit.

### Repository disconnection

Revocation of a repository's scanning connection while retaining authorized historical evidence.

### Repository archival

Retirement of a repository from active presentation while preserving its evidence and unresolved historical exposure.

### Tenant erasure

The verified removal of an organization's data across active stores and retained copies, with separate progress for active-store removal and backup expiration.

### Duplicate group

A human-established group of findings representing the same issue, with one canonical target and retained evidence from every member. Its exposure remains unresolved while any member has unresolved obligations.

### Advisory lineage

The verified relationship between dependency findings involving the same package and advisory across installed versions. A vulnerable upgrade preserves exposure continuity without automatically carrying over human dispositions.

### Superseded automatic scan

An accepted automatic scan replaced before execution by a newer descendant request within the same branch generation. Its retained record identifies skipped coverage and contributes no finding observations.

### Repository security operations

The primary product wedge for ScanForge: helping internal engineering and security teams manage repository security work from onboarding through scanning, normalized finding review, triage, evidence, reporting, and auditability.

### Scan lifecycle

The progression of a scan from creation through queueing, worker execution, scanner runs, raw artifact handling, normalized finding persistence, completion, failure, retry, or dead-letter handling.

### Dedicated worker

A worker host assigned to one organization for the secure private beta.

### Scan containment

The disposable execution boundary around scanner commands for one scan.

### Worker identity

An organization-scoped service principal used by a dedicated worker when it calls internal API routes.

### Scan execution contract

The record of what a scan was expected to execute, what actually ran, what failed, and whether the result is complete enough to update finding workflow states.

### Scanner health

The trust signal for an individual scanner's availability, execution result, output parsing, timeout or error state, and contribution to scan coverage.

### Scanner output normalization

The conversion of scanner-specific raw output into canonical finding candidates before durable finding persistence.

### Canonical finding persistence

The durable record of findings, their scan-specific occurrences, references, and lifecycle events.

### Deduplication policy

The domain rules that decide whether scanner output represents a new finding, another occurrence of an existing finding, or a reappearance of a previously fixed finding.

### Not observed finding

A finding that was previously seen but was absent from a later relevant scan without yet being proven fixed.

### Finding workflow state

The explicit review and remediation state of a finding, separate from the action or event that changed it.

### Finding lifecycle policy

The domain policy that defines finding workflow states, allowed transitions, disappearance handling, deduplication behavior, scanner coverage requirements, and when finding state may be changed automatically.

### Risk score

A prioritization signal expressing a finding's assessed risk using documented evidence and context.

### Repository importance

The business or operational importance of a repository or project for prioritizing security work.

### SLA policy

The remediation expectation for findings based on their risk, severity, workflow state, ownership, and relevant project or repository context.

### Scorecard

The security-program view of repository security operations.

### Policy evaluation

The assessment of findings, scans, repositories, or projects against security rules without necessarily enforcing those rules.

### AI assistance

The use of AI to help users understand, triage, or remediate security findings.

### MCP interface

An agent-facing interface over ScanForge capabilities.

### Raw artifacts visibility

Authorized access to sanitized scanner artifacts supporting finding evidence, debugging, and auditability.

### Access

The organization, project, repository, and role checks that decide whether a user may view or mutate ScanForge resources.

### Repository onboarding

The progression from organization membership and GitHub connection through repository connection, first scan, and finding review.
