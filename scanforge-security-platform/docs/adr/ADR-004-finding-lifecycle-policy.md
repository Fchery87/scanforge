# ADR-004: Finding lifecycle policy

## Status

Accepted

## Context

ScanForge normalizes scanner output into long-lived findings and per-scan finding instances. That model is only useful if finding state changes mean the same thing everywhere they appear: API routes, worker persistence, scan history, scorecards, exports, notifications, and future developer workflows.

The simple approach is to treat every missing finding as fixed and every non-actionable finding as suppressed. That is unsafe for ScanForge because scanner coverage can vary by scan type, branch, path scope, scanner failure, disabled scanner, or rule changes. A finding can disappear because the underlying issue was remediated, but it can also disappear because the relevant scanner did not run or the scan was not comparable.

The current terminology also risks overloading user actions and finding states. Suppression, false positive, accepted risk, duplicate, and fixed are different decisions with different audit, SLA, reporting, and remediation consequences.

## Decision

Create a formal finding lifecycle policy before implementing broad workflow-state changes.

Finding workflow state should be explicit and separate from the event or action that changed it. ScanForge should distinguish states such as open, reviewing, to fix, accepted risk, false positive, duplicate, not observed, and fixed.

Not observed is a first-class state for findings that were previously seen but absent from a later relevant scan without yet being proven fixed. Fixed should require policy-defined evidence, not mere absence from one scan.

Automatic workflow-state changes must depend on the scan execution contract and scanner health. A finding should not become not observed or fixed unless the relevant scanner ran successfully with equivalent coverage and comparable rules for the relevant repository, branch, scan type, and path scope.

Deduplication policy should remain a tunable domain capability. Repository-scoped canonical fingerprints are the starting default, but future behavior may become scanner-aware, branch-aware, or scope-aware.

Risk score and SLA policy should consume finding lifecycle state rather than replace it. External issue creation should project from stable finding workflow state instead of becoming the source of truth for remediation.

## Consequences

Future finding-state work should start from the finding lifecycle policy, not from individual UI actions or route handlers.

Future scan lifecycle work must preserve enough scanner execution detail for finding lifecycle decisions to be safe.

Scorecards, exports, notifications, and SLA reporting should treat accepted risk, false positive, duplicate, not observed, and fixed as distinct outcomes.

Developer PR workflows and future policy gates should use the same finding lifecycle semantics as centralized triage.

AI assistance and MCP interfaces should avoid mutating lifecycle state until authorization, auditability, and transition rules are mature.

## Implementation Guidance

The first implementation slice should define the allowed finding workflow states and transition rules in one domain module.

The next slice should make scan completion record scanner coverage and scanner health well enough to decide whether finding disappearance is meaningful.

Only after those slices should ScanForge implement automatic movement into not observed or fixed.

Existing statuses may need migration or compatibility mapping, but new product behavior should use explicit workflow states rather than overloaded suppression semantics.
