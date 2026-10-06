# ADR-010: Evidence comparability and disappearance policy

## Status

Accepted for the private beta

## Context

ADR-004 requires comparable scanner evidence before automatic finding lifecycle transitions, but it does not define the evidence contract in enough detail for the completion and triage services to enforce it consistently. A worker-supplied `coverage_comparable` flag is insufficient: it can be stale, forged, or based on scanner metadata that the API never persisted.

A finding can also be observed on more than one branch. An absence on one branch must not satisfy the evidence obligation for another branch, and a repeated delivery of the same commit must not count as a second observation. Legacy scans without scanner provenance must remain useful as history but cannot retroactively prove a clean or comparable scan.

## Decision

### Authority and ownership

- The API owns scan completion, scanner health, scanner provenance, accepted finding instances, lifecycle transitions, and derived summary fields.
- `seen_fingerprints`, scanner health, coverage completeness, and comparability are derived from accepted request data and persisted rows. Worker summary values are informational input only and never authorize a transition.
- A completion is operationally complete when every expected scanner has an explicit completed or failed run. Partial health is visible and terminal, but never authorizes disappearance or closure.
- A scan is eligible for disappearance only when it is a full scan with a persisted branch ref, commit SHA, complete expected scanner set, and API-derived comparable coverage.

### Comparability and provenance

A scanner run is comparable only when the API has persisted:

1. a successful scanner result;
2. a non-empty scanner version; and
3. at least one explicit provenance value for the relevant rules version, vulnerability-database version, or configuration digest.

Unknown, missing, or legacy provenance is incomparable. A worker cannot promote unknown provenance by setting a summary boolean. Diff scans remain non-closing because their path scope is not repository-wide.

This is a conservative beta policy. A future compatibility registry may establish equivalence across scanner or rules updates, but unknown compatibility remains non-closing until that registry is accepted and tested.

### Branch and commit obligations

- Presence records the finding's observed branch in its persisted metadata.
- Absence evidence is stored per branch and contains the scan ID and commit SHA.
- The same commit can count only once, regardless of retries or duplicate delivery.
- A finding must have qualifying absence evidence for every observed branch before an automatic transition can occur. An unrelated branch cannot close another branch's finding.
- Reappearance on a branch clears that branch's absence series and reopens an automatically absent finding.
- A manual reopen clears all absence series and records a timestamp checkpoint. Scans at or before that checkpoint cannot immediately re-close the finding.

### Transition policy

- `open` plus one distinct qualifying absence becomes `not_observed`.
- `not_observed` plus the configured second distinct qualifying absence becomes `fixed`.
- Human-controlled states such as reviewing, accepted risk, false positive, duplicate, and manually fixed are not changed by the automatic absence evaluator.
- Every automatic transition or recorded blocked absence retains policy version, scan ID, branch, commit, threshold, and reason/evidence metadata in `FindingEvent`.
- The beta threshold is two distinct qualifying full scans (`scan-evidence-v1`).

### Replay and atomicity

The server-issued attempt ID, execution revision, and durable completion receipt define completion identity. An identical replay returns the accepted response; a different payload for the same identity is rejected. Scanner runs, finding instances, lifecycle events, derived summary, and terminal status are committed in one transaction.

## Consequences

- Legacy rows remain queryable but cannot authorize automatic disappearance until a new scan supplies complete provenance.
- A scanner integration must send scanner version and rules/database/configuration provenance before it can contribute to automatic closure.
- Some operationally successful scans will intentionally produce no lifecycle transition. The UI and summaries must expose incomplete or incomparable evidence rather than imply remediation.
- PostgreSQL, worker, and staging evidence is still required before this policy is a release-complete readiness result; unit and SQLite tests do not substitute for those receipts.

## Verification matrix

| Scenario | Operational result | Lifecycle result |
| --- | --- | --- |
| Full scan, all runs complete, comparable provenance | Completed | May record one branch-local absence |
| Partial or failed scanner run | Completed with partial health | No absence or closure |
| Missing scanner run | Rejected or partial, per completion contract | No absence or closure |
| Diff scan | Completed | No repository-wide absence |
| Empty full result with unknown provenance | Completed | No absence or closure |
| Same commit delivered twice | Replay/idempotent | Counts once |
| Finding present in accepted instance | Completed | Absence series reset |
| Finding absent on unrelated branch | Completed | Other branch remains open |
| Manual reopen followed by old scan | Completed | Checkpoint blocks re-close |
