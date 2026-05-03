# Documentation Guide

This directory contains the current operational documentation for ScanForge.

## Start Here

- `../README.md`: primary repository overview, architecture, setup, and current status
- `CODE_REVIEW.md`: current engineering review findings and risk summary
- `SYSTEM_OVERVIEW.md`: runtime topology and end-to-end request and scan flow
- `development-setup.md`: local setup and day-to-day development workflow
- `scanner-setup.md`: scanner installation notes and local verification

## Supporting Sections

- `adr/`: architecture decisions worth preserving long-term
- `adr/ADR-003-scan-lifecycle-architecture-program.md`: scan lifecycle module ownership and adjacent module decisions
- `adr/ADR-004-finding-lifecycle-policy.md`: finding workflow state, not observed handling, and lifecycle transition policy
- `plans/`: historical or in-progress work plans that may still be useful for context
- `plans/2026-05-02-scan-lifecycle-architecture-program.md`: vertical slice plan for deepening the scan lifecycle architecture
- `plans/2026-05-02-module-first-security-operations-roadmap.md`: module-first roadmap for repository security operations improvements
- `neon-setup.md`: Neon-specific setup notes

## Source Of Truth

The repository root `README.md` and files in this folder should be treated as the current documentation set.

Older scaffold-era planning files have been removed when they no longer matched the codebase.
