# ADR-010: Managed beta release scope and evidence

## Status

Accepted on 2026-10-16 during the roadmap grilling session.

## Decision

The next release proves repository security operations for security reviewers in an invitation-only cohort of three to five organizations, with operator-managed onboarding. Developer PR review follows a reliable centralized scanning and triage workflow. This preserves the sequencing in CONTEXT.md and the dedicated-worker architecture in ADR-009.

ScanForge temporarily clones private source into its managed, isolated execution infrastructure. Customer-hosted execution is deferred. External AI processing requires explicit organization opt-in and verified data boundaries; AI remains disabled in the initial managed beta.

Incomplete features may be hidden or disabled until their acceptance criteria pass. Every review finding must have an explicit disposition: fix before release, defer with the affected feature disabled, or replace through an accepted design. Authorization defects, lost findings, incorrect commit attribution, and misleading success states block release of the affected workflow.

Release requires evidence from the actual deployment topology: scanner containers, PostgreSQL, queue recovery, a GitHub test installation, and authenticated browser workflows. Required scenarios include known-positive and clean scans, partial scanner failure, cancellation, worker crash recovery, replay, and cross-organization denial. Evidence identifies the tested revision and deployed artifacts.

## Rationale and consequences

This scope prioritizes trustworthy security evidence over launching every visible feature or public self-service onboarding. It permits a smaller useful beta while preserving the longer-term AI-assisted code-review goal. Unit tests and document completion labels do not establish release readiness.

This ADR accepts product scope and the release evidence requirement only. It does not approve unmeasured payload limits, recovery timings, retention policy, or the proposed execution semantics in the September scan-evidence decision table. Those remain subjects for the interview and implementation validation.
