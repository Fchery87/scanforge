# ADR-018: Developer-first repository security and pull-request review direction

## Status

Accepted on 2026-11-04. Supersedes the audience and positioning in [ADR-010](ADR-010-managed-beta-release-scope.md). ADR-010's release-evidence requirements remain in force. ADR-011 through ADR-017 remain in force.

## Context

ADR-010 positioned the next release as managed repository security operations for security reviewers in an invitation-only cohort, with developer PR review following later. The [product charter](../PRODUCT_CHARTER.md) redirects ScanForge toward small engineering teams with multiple GitHub repositories and limited security staffing, centred on this workflow: establish a trustworthy baseline, identify risks introduced by changes, present actionable evidence, and verify remediation over time.

By 2026-11-04 the managed-beta work had landed source attribution, contained scanner execution, evidence contracts, repository authority and durable dispatch (October tasks M00–M07). Those foundations serve both audiences.

## Decision

1. **Audience.** The primary user is a developer on a small engineering team. Security reviewers remain supported users of triage and history. The 3–5 organization pilot cohort remains, but it is selected from teams matching the charter's customer hypothesis.
2. **Sequencing is preserved.** A trustworthy scanner-backed baseline comes before PR review, and PR review starts private (shadow mode) before any publication. ADR-010 already required this order.
3. **Milestone.** The next milestone is a scanner-backed PR review running in shadow mode on real repositories, beginning with ScanForge's own repository, that records coverage and cost, understands one framework, and reconciles results across commits.
4. **Boundaries.** Advisory only; no merge gates on unverified output; no auto-commit, auto-merge, dependency installation or autonomous remediation; no general style review; GitHub only; no infrastructure rewrite without measured need.
5. **Authority.** The charter is the product direction. ADRs record accepted decisions. A single implementation plan in `docs/plans/` owns execution order. Where the charter and an accepted ADR disagree, the ADR governs until a new ADR changes it.

## Consequences

- `pr_review` and `diff_scans` remain disabled in the beta capability policy until the plan's shadow-mode gate passes. Shadow execution must not publish to GitHub.
- The October implementation plan is closed and archived. Its unfinished tasks are re-triaged as pilot-blocking or deferred in the active plan.
- Dedicated per-organization hosts (ADR-009/ADR-011) remain for the pilot. Whether that operating model serves small teams economically is an open question to measure during the pilot, not a reason to rebuild now.
- Numeric AI-quality thresholds are set from shadow-mode baseline data. The October plan's ">=90% precision / >=80% recall" entry gate for AI code review is treated as a candidate target pending that data, not an accepted threshold.
