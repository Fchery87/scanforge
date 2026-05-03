# Module-First Security Operations Roadmap

## Vision

ScanForge should improve as a repository security operations platform before broadening into generic vulnerability management, cloud posture, AI remediation, MCP, or additional SCM providers.

The near-term product goal is a trustworthy centralized triage workflow for internal engineering and security teams. That requires reliable scan lifecycle behavior, explicit finding lifecycle semantics, scanner-level trust signals, transparent prioritization, and security-program reporting.

## Success Criteria

- Manual scans, scheduled scans, and future scan triggers use one scan lifecycle path.
- Queue payloads carry minimal validated execution identity and do not duplicate authoritative scan context.
- Scan completion records enough execution detail to distinguish complete, partial, failed, skipped, and incomparable scanner coverage.
- Finding workflow states are explicit and not overloaded through suppression semantics.
- Findings move to not observed or fixed only when scanner coverage and policy evidence support that transition.
- Risk score, repository importance, and SLA policy produce transparent advisory prioritization.
- Scorecards explain security-program exposure, trend direction, SLA pressure, and scanner reliability.
- GitHub PR workflow remains advisory until policy evaluation and scan trust are mature.

## Key Risks

- Queue and worker contracts drift again if payload shape is not centralized and validated.
- Automatic finding-state changes can create false confidence if scanner coverage is incomplete.
- Workflow-state migration can break existing UI filters, exports, and tests if compatibility mapping is not explicit.
- Risk score can lose trust if it is opaque or overclaims unavailable signals such as reachability.
- Policy gates can harm developer trust if enforcement starts before scanner health and deduplication are reliable.

## Proof Strategy

Use thin vertical slices that each cut through domain policy, persistence, API behavior, worker behavior where relevant, UI visibility, and tests. Early slices retire the hardest correctness risks before adding prioritization, scorecards, PR workflow, or AI-facing surfaces.

## Slices

- [x] **S01: Stabilize Scan Creation Contract** `risk:high` `depends:[]`
  > After this: manual and scheduled scans create one consistent scan lifecycle outcome and enqueue one minimal, validated queue payload.

- [x] **S02: Record Scan Execution Contract** `risk:high` `depends:[S01]`
  > After this: each scan records expected scanners, actual scanner runs, failures, skipped scanners, scan type, branch, and coverage scope well enough to judge result completeness.

- [x] **S03: Separate Scanner Health From Scan Status** `risk:high` `depends:[S02]`
  > After this: the UI/API can show a completed scan with partial scanner failure instead of hiding scanner-level trust problems behind scan status.

- [x] **S04: Define Finding Workflow States** `risk:high` `depends:[]` `hitl:yes`
  > After this: findings have explicit lifecycle states like open, reviewing, to fix, accepted risk, false positive, duplicate, not observed, and fixed, with transition rules centralized in one domain path.

- [x] **S05: Add Not Observed Handling** `risk:high` `depends:[S02,S03,S04]`
  > After this: a previously seen finding can move to not observed only when the relevant scanner coverage was complete and comparable.

- [x] **S06: Add Fixed Promotion Policy** `risk:medium` `depends:[S05]` `hitl:yes`
  > After this: findings become fixed only after policy-defined evidence, such as repeated relevant successful scans, rather than a single disappearance.

- [x] **S07: Introduce Transparent Risk Score** `risk:medium` `depends:[S04]`
  > After this: findings can be sorted by a visible risk score using severity, confidence, age, workflow state, and repository or project importance.

- [x] **S08: Add Repository Importance Signal** `risk:medium` `depends:[S07]` `hitl:yes`
  > After this: projects or repositories can be classified as critical, high, normal, or low, and that signal affects risk score output.

- [x] **S09: Add SLA Policy Preview** `risk:medium` `depends:[S04,S07,S08]` `hitl:yes`
  > After this: findings show advisory SLA status based on workflow state, risk or severity, assignment, due date, and repository importance.

- [x] **S10: Upgrade Scorecard Around Risk And Reliability** `risk:medium` `depends:[S03,S07,S09]`
  > After this: scorecards report exposure, trend direction, SLA pressure, scanner health, noisy scanners, and high-risk repositories or projects.

- [x] **S11: Add Advisory Policy Evaluation** `risk:medium` `depends:[S03,S07,S09]` `hitl:yes`
  > After this: users can see whether a scan or repository would fail a policy without blocking PRs or merges.

- [x] **S12: Add GitHub PR Workflow Foundation** `risk:medium` `depends:[S01,S02,S04,S11]`
  > After this: GitHub webhooks and diff scans can attach advisory results to PR context without hard enforcement.

- [x] **S13: Add Remediation Guidance Surface** `risk:low` `depends:[S04,S07]`
  > After this: finding detail pages show structured remediation guidance based on scanner evidence and references before any AI or autofix work.

- [x] **S14: Final End-To-End Reliability Pass** `risk:high` `depends:[S01,S02,S03,S04,S05,S06,S07,S08,S09,S10,S11,S12,S13]`
  > After this: one repository can be onboarded, scanned, partially fail a scanner, persist trustworthy findings, update lifecycle states safely, show risk/SLA/scorecard signals, and produce advisory PR or policy feedback.

## Boundary Map

### S01 Produces

One scan lifecycle entry point for scan creation and enqueue behavior. Queue payloads contain execution identity and immutable hints only.

### S01 Consumed By

S02 and S12 consume the stable scan creation contract so worker execution and GitHub PR workflows do not invent alternate scan payload semantics.

### S02 Produces

A scan execution contract that records expected scanners, actual scanners, failures, skipped scanners, scan type, branch, and coverage scope.

### S02 Consumed By

S03 consumes execution detail for scanner health display. S05 consumes it to decide whether missing findings can become not observed. S12 consumes it for PR advisory feedback.

### S03 Produces

Scanner health as a distinct trust signal from scan status.

### S03 Consumed By

S05, S10, and S11 consume scanner health to avoid overstating finding status, scorecard quality, or policy results.

### S04 Produces

Canonical finding workflow states and transition rules.

### S04 Consumed By

S05, S07, S09, S12, and S13 consume workflow states for disappearance handling, prioritization, SLA previews, PR feedback, and remediation guidance.

### S05 Produces

Not observed handling gated by scanner coverage and scan comparability.

### S05 Consumed By

S06 consumes not observed as the prerequisite state for fixed promotion.

### S06 Produces

Fixed promotion policy based on repeated or otherwise sufficient evidence.

### S06 Consumed By

S14 consumes fixed promotion behavior for final end-to-end validation.

### S07 Produces

Transparent risk score using available signals without claiming unavailable reachability or runtime context.

### S07 Consumed By

S08, S09, S10, S11, and S13 consume risk score for repository importance weighting, SLA previews, scorecards, policy evaluation, and guidance ordering.

### S08 Produces

Repository or project importance classification.

### S08 Consumed By

S09 and S10 consume importance for SLA and scorecard prioritization.

### S09 Produces

Advisory SLA policy status.

### S09 Consumed By

S10 and S11 consume SLA status for scorecards and advisory policy evaluation.

### S10 Produces

Security-program scorecard views grounded in risk, SLA pressure, and scanner reliability.

### S10 Consumed By

S14 consumes scorecard behavior for final integration proof.

### S11 Produces

Read-only policy evaluation results.

### S11 Consumed By

S12 consumes advisory policy results for GitHub PR feedback without enforcement.

### S12 Produces

GitHub PR workflow foundation for advisory diff and policy feedback.

### S12 Consumed By

S14 consumes GitHub PR behavior for final integration proof.

### S13 Produces

Structured remediation guidance on finding detail surfaces.

### S13 Consumed By

Future AI assistance and MCP interfaces can consume guidance once domain semantics are stable.

## Verification Classes

- Unit tests for lifecycle transition rules, queue payload validation, risk score calculation, SLA preview logic, and policy evaluation.
- Integration tests for API scan creation, worker scan execution updates, finding persistence, and scanner health recording.
- Regression tests for existing finding filters, triage actions, exports, scorecards, and audit events.
- End-to-end smoke test for repository onboarding through scan completion and centralized triage review.

## Definition Of Done

- All slices preserve the repository security operations product wedge.
- No slice introduces generic manual scan import, broad ASPM asset modeling, hard policy enforcement, auto-remediation pull requests, or new SCM provider breadth.
- Every automatic finding-state change is justified by scanner health and scan execution contract data.
- Every user-facing lifecycle state has corresponding audit or event history.
- Validation commands fail loudly when checks fail.

## Requirement Coverage

- Repository security operations focus: S01 through S14.
- Centralized triage first: S04 through S10.
- Scan lifecycle reliability: S01 through S03 and S14.
- Explicit finding lifecycle policy: S04 through S06.
- Risk and SLA prioritization: S07 through S10.
- Advisory policy before enforcement: S11 and S12.
- GitHub depth before SCM breadth: S12.
- AI guidance before mutation: S13.

## Horizontal Checklist

- Access checks remain outside scan lifecycle ownership.
- Raw artifacts remain secondary to structured evidence.
- Scanner output normalization remains separate from canonical finding persistence.
- Existing statuses receive compatibility mapping before destructive migration.
- Documentation stays aligned with `CONTEXT.md` and accepted ADRs.
