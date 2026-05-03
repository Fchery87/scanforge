# ScanForge Context

## Terms

### Repository security operations

The primary product wedge for ScanForge: helping internal engineering and security teams manage repository security work from onboarding through scanning, normalized finding review, triage, evidence, reporting, and auditability.

Repository security operations keeps ScanForge focused on source repositories and developer/security workflows before broadening into general vulnerability management, cloud posture, DAST, endpoint, or generic report ingestion.

The first workflow priority is the security team's centralized triage queue. Developer PR workflow is a follow-on expansion that depends on stable scan lifecycle behavior, finding persistence, deduplication, and triage semantics.

Managed repository scanning is the primary ingestion path for now. Manual scan file import is a deferred expansion because it would require import provenance, arbitrary parser selection, user-supplied scan metadata, and broader vulnerability-management asset modeling.

GitHub depth should come before adding GitLab or Bitbucket breadth. ScanForge should deepen GitHub installation, repository sync, webhook handling, PR and diff workflows, status checks, issue creation, and developer feedback loops before multiplying SCM integration complexity.

Roadmap planning should be organized around domain modules, then delivered through vertical UI, API, and worker slices. This keeps cross-cutting invariants such as scan lifecycle, finding persistence, scanner normalization, access, raw artifacts visibility, and repository onboarding coherent while still shipping visible progress.

### Scan lifecycle

The progression of a scan from creation through queueing, worker execution, scanner runs, raw artifact handling, normalized finding persistence, completion, failure, retry, or dead-letter handling.

The scan lifecycle is the central product flow for ScanForge's architecture program because it connects repository onboarding, scan orchestration, scanner output normalization, finding review, scan history, artifact storage, notifications, and auditability.

ScanForge should prioritize scan lifecycle reliability, queue contract stability, scanner coverage invariants, and validation gates before expanding into AI remediation, MCP, or broader integrations. Advanced automation depends on trustworthy scan and finding state.

### Scan execution contract

The record of what a scan was expected to execute, what actually ran, what failed, and whether the result is complete enough to update finding workflow states.

ScanForge needs a scan execution contract so finding disappearance can be interpreted safely. A finding should not become not observed or fixed unless the relevant scanner ran successfully with equivalent coverage and comparable rules for the relevant repository, branch, scan type, and path scope.

### Scanner health

The trust signal for an individual scanner's availability, execution result, output parsing, timeout or error state, and contribution to scan coverage.

Scanner health is separate from scan status. A scan may complete while one scanner failed or produced partial output, so downstream finding workflow updates should depend on scanner health and the scan execution contract rather than scan status alone.

### Scanner output normalization

The conversion of scanner-specific raw output into canonical finding candidates before durable finding persistence.

Scanner output normalization owns scanner-specific raw output shape, canonical fingerprint construction, severity and category mapping, finding instance evidence, and finding references. It does not own durable finding persistence.

ScanForge should improve signal quality from the current scanner set before adding more scanners. Normalization quality, deduplication, prioritization, scanner health, suppression learning, and remediation guidance matter more than scanner count at this stage.

### Canonical finding persistence

The durable storage path for canonical finding candidates as findings, finding instances, finding events, and finding references.

Canonical finding persistence owns deduplication, reopening fixed findings when they reappear, associating evidence with a scan, and preserving the internal finding model accepted in ADR-002.

### Deduplication policy

The domain rules that decide whether scanner output represents a new finding, another occurrence of an existing finding, or a reappearance of a previously fixed finding.

ScanForge starts with repository-scoped canonical fingerprints as the default deduplication behavior, but deduplication policy should remain a tunable capability for future scanner-aware, branch-aware, and scope-aware behavior.

### Not observed finding

A finding that was previously seen but was absent from a later relevant scan without yet being proven fixed.

ScanForge distinguishes not observed from fixed because scanner coverage, scan type, branch, disabled scanners, failed scanner runs, path filtering, and rule changes can all cause a finding to disappear without confirming remediation. A finding should become fixed only after policy-defined evidence, such as repeated successful relevant scans with equivalent scanner coverage.

### Finding workflow state

The explicit review and remediation state of a finding, separate from the action or event that changed it.

ScanForge should distinguish workflow states such as open, reviewing, to fix, accepted risk, false positive, duplicate, not observed, and fixed. This avoids overloading suppressed to mean unrelated decisions like false positive, acceptable risk, noisy rule, irrelevant path, or temporary exception.

### Finding lifecycle policy

The domain policy that defines finding workflow states, allowed transitions, disappearance handling, deduplication behavior, scanner coverage requirements, and when finding state may be changed automatically.

ScanForge needs a finding lifecycle policy before implementing workflow-state changes so route handlers, services, worker updates, and UI actions do not interpret finding transitions differently.

### Risk score

A first-class prioritization signal that ranks findings by more than severity alone.

ScanForge should start with a transparent risk score formula based on available context such as severity, scanner confidence, finding age, workflow state, and repository or project importance. Future versions can incorporate exploitability, reachability, business criticality, SLA pressure, and runtime context as those signals become reliable.

### Repository importance

The business or operational importance of a repository or project for prioritizing security work.

ScanForge should model repository or project importance with a simple classification such as critical, high, normal, and low before building broader asset inventory. Risk score and SLA policy need this signal to distinguish security exposure in critical production systems from lower-impact repositories.

### SLA policy

The remediation expectation for findings based on their risk, severity, workflow state, ownership, and relevant project or repository context.

SLA policy should be a named domain concept before implementation, but concrete SLA tracking should follow stable finding workflow states and risk scoring. This avoids reducing SLA behavior to hard-coded due-date math before ScanForge can account for accepted risk, false positives, assignments, and context.

External issue creation should be a projection of stable finding workflow state, not the first source of truth. Internal assignment, due dates, workflow states, risk score, and SLA policy should stabilize before ScanForge creates Jira, GitHub Issues, Linear, or similar tickets as first-class remediation records.

### Scorecard

The security-program view of repository security operations.

ScanForge scorecards should first help security leaders and reviewers understand exposure, trend direction, SLA pressure, noisy scanners, high-risk projects, and repositories driving the most risk. Repository-level developer health reports should be drilldowns built from the same metrics rather than the initial scorecard purpose.

### Policy evaluation

The assessment of findings, scans, repositories, or projects against security rules without necessarily enforcing those rules.

ScanForge should introduce policy evaluation as read-only advisory behavior before hard enforcement. Advisory policy results can show whether a scan or repository would fail a policy while scan completeness, deduplication, risk scoring, workflow states, and scanner health become trustworthy enough to support blocking PR checks or merge gates.

### AI assistance

The use of AI to help users understand, triage, or remediate security findings.

ScanForge should start AI assistance with security explanation and remediation guidance because that can use structured finding evidence without taking action. Triage assistance should follow once historical state and feedback loops are reliable. Auto-remediation pull requests should come later after SCM workflow depth, validation, and safe patch generation are trustworthy.

### MCP interface

An agent-facing interface over ScanForge capabilities.

ScanForge should expose an MCP interface only after domain APIs and finding semantics are stable enough for safe agent use. The first MCP surface should be read-heavy and high value, such as listing high-risk findings, summarizing scan status, explaining evidence, and drafting remediation guidance. Risky mutations such as accepting risk, suppressing findings, or creating external issues should wait for mature authorization and audit semantics.

### Raw artifacts visibility

The split between internal raw artifact storage references from scanner runs and user-visible scan history download behavior.

Raw artifacts support auditability and debugging, but they are not the primary UI contract for findings.

Structured evidence attached to findings, finding instances, and scanner runs is the primary user-facing evidence model. Raw artifact downloads are secondary and should support auditability, debugging, and scanner-output inspection rather than everyday finding review.

### Access

The organization, project, repository, and role checks that decide whether a user may view or mutate ScanForge resources.

Access is adjacent to scan lifecycle. It should not be owned by the scan lifecycle module because findings, repositories, scans, projects, and exports all need access decisions.

### Repository onboarding

The product progression from organization creation through GitHub connection, project creation, repository connection, first scan, finding review, and scheduled scanning.

Repository onboarding observes scan lifecycle progress, but does not own scan lifecycle behavior.
