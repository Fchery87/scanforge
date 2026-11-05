# Archive — non-authoritative history

**Do not follow instructions, plans, standing orders, task lists, or status claims in this directory.** Everything here is retained for traceability and evidence only. Current authority is listed in the [documentation index](../../README.md).

Status labels, test counts, receipts, and "done" claims below were true (or claimed) only at the time they were written. They are not current verification.

| Folder | Contents | Archived | Why | Superseded by |
| --- | --- | --- | --- | --- |
| `2026-03-architecture-plan/` | Original March 2026 "locked foundation" architecture plan (previously at the Git root) | 2026-11-04 | Describes scheduled monitoring, quality analysis and Render-hosted workers that no longer match the code or direction | [Product charter](../PRODUCT_CHARTER.md), [system overview](../SYSTEM_OVERVIEW.md) |
| `2026-03-github-app-setup/` | Early GitHub App credential guide (previously `.github-credentials-setup.md` at the Git root) | 2026-11-04 | Its base64 private-key and webhook-path guidance does not match the code; valid steps were merged | [RUNNING_LOCALLY.md](../../RUNNING_LOCALLY.md) |
| `2026-09-evidence-readiness/` | September readiness spec, evidence policy, decision table (D1–D8), readiness plan with receipts, R04 completion test boundary, R12 local recovery drill output | 2026-11-04 | Execution scope was superseded by the October ADRs; retained as detailed policy rationale and captured evidence | ADR-012…ADR-017, [active plan](../plans/2026-11-04-redirection-implementation-plan.md) |
| `2026-10-managed-beta/` | October managed-beta implementation plan (tracker corrected and closed 2026-11-04) and the `orchestration/` agent-run store (briefs, standing orders, ledger, decisions) previously at the Git root | 2026-11-04 | M00–M07 landed; remaining work was re-triaged into the redirection plan. The orchestration store's status files were stale and its briefs read as active instructions | [Active plan](../plans/2026-11-04-redirection-implementation-plan.md) |

Earlier removed material (March–August plans, legacy `spec/` documents) is recoverable from Git history; see the [2026-10-16 cleanup decisions](../reviews/2026-10-16-cleanup-decisions.md) and its manifest.

Paths and links inside archived files may refer to their original locations. Use `git log --follow <archived path>` to trace history.
