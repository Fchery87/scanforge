# Roadmap

## Current release priority

| Phase | Scope | Execution tracker |
| --- | --- | --- |
| Private-beta readiness | Evidence integrity, isolation, release checks, GitHub workflow, and operational proof | [Evidence-first readiness plan](../docs/plans/2026-09-13-evidence-first-readiness-plan.md) |

Use the active plan before expanding product breadth. The [readiness spec](2026-09-13-evidence-first-readiness.md)
remains proposed where it adds architecture details. Existing accepted ADRs and the approved beta scope still apply.
The phase list below records the earlier product sequence, not current completion evidence.

## Phase 0 | Foundation
- repo scaffold
- environment configuration
- database models and migrations
- auth integration
- health/readiness endpoints

## Phase 1 | Core product MVP
- org/project/repository setup
- scan creation API
- worker queue loop
- Trivy, Gitleaks, and OSV adapters
- findings normalization
- dashboard and findings views
- export and audit log basics

## Phase 2 | Monitoring and governance
- scheduled scans
- suppression workflows
- notifications
- scorecards
- richer filtering and search

## Phase 3 | Broader coverage
- Syft/Grype integration
- Checkov
- Semgrep CE
- more reporting
- policy evaluation

## Phase 4 | Future
- MCP server
- AI remediation
- PR diff scanning
- advanced governance
