# Documentation cleanup report — 2026-11-04

## Authorization

The user approved the discovery report's disposition plan and decisions D1–D5 as recommended ("go with your strongest recommendation"), with D5 revised to a SYSTEM_OVERVIEW section instead of a new file. Work is on branch `docs/product-redirection` from `main` at `f5a47dd`, uncommitted pending review.

## Decisions applied

| ID | Decision |
| --- | --- |
| D1 | [ADR-018](../adr/ADR-018-developer-first-security-review-direction.md) supersedes ADR-010's audience/positioning; ADR-010 release-evidence requirements remain |
| D2 | Reversible archival under `docs/archive/` with a non-authoritative README. Zero deletions. This overrides the 2026-10-16 Q8/Q13 "no archive folder" choice for this cleanup only |
| D3 | October plan tracker corrected, plan closed and archived; single new [redirection implementation plan](../plans/2026-11-04-redirection-implementation-plan.md) |
| D4 | Charter moved from `docs/plans/scanforge-product-redirection-v2.md` (untracked) to [docs/PRODUCT_CHARTER.md](../PRODUCT_CHARTER.md), content unchanged |
| D5 | Trust boundaries and the capability matrix added to [SYSTEM_OVERVIEW](../SYSTEM_OVERVIEW.md); no separate security-model file |

## Moves (all `git mv` except the untracked charter)

| From | To |
| --- | --- |
| `ScanForge-architecture-implementation-plan.md` (Git root) | `docs/archive/2026-03-architecture-plan/` |
| `.github-credentials-setup.md` (Git root) | `docs/archive/2026-03-github-app-setup/github-credentials-setup.md` |
| `orchestrate/managed-beta/**` (21 files, Git root) | `docs/archive/2026-10-managed-beta/orchestration/` |
| `docs/plans/2026-10-16-managed-beta-implementation-plan.md` | `docs/archive/2026-10-managed-beta/` (tracker corrected first) |
| `docs/plans/2026-09-13-evidence-first-readiness-plan.md`, `r04-completion-test-boundary.md`, `r12-recovery-drill-runbook.md` | `docs/archive/2026-09-evidence-readiness/` |
| `spec/2026-09-13-{evidence-first-readiness,scan-evidence-policy,scan-evidence-decisions}.md` | `docs/archive/2026-09-evidence-readiness/` |
| `docs/plans/scanforge-product-redirection-v2.md` (untracked) | `docs/PRODUCT_CHARTER.md` |

The empty `orchestrate/` and `spec/` directories were removed with `rmdir`.

## Edits

| File | Change |
| --- | --- |
| `../AGENTS.md` | Read order (charter → ADRs → overview → plan); archive is non-authoritative; tracker-in-same-commit rule |
| `README.md` | Rewritten as the single documentation index |
| `CONTEXT.md` | Authority pointers; "managed security operations beta" replaced by Pilot cohort; wedge entry reworded; added Shadow review, Analysis run, Observation, Persistent finding, Review comment, Comparable analysis, Coverage assessment, Effective configuration |
| `docs/SYSTEM_OVERVIEW.md` | Re-verified B1–B12 status; deployment topology; trust boundaries; capability matrix; new gaps G1–G7 |
| `docs/adr/ADR-010-…md` | Status line notes partial supersession |
| `docs/adr/ADR-018-…md` | New |
| `docs/agents/domain.md` | Charter and overview added to read order; archive rule |
| `docs/archive/README.md` | New; non-authoritative notice and folder index |
| `docs/archive/2026-10-managed-beta/2026-10-16-managed-beta-implementation-plan.md` | Status closed; M05/M06 Done, M07 landed-unverified, M08 partial, with commits |
| `docs/plans/2026-11-04-redirection-implementation-plan.md` | New active plan |
| `RUNNING_LOCALLY.md` | Merged GitHub App creation steps, corrected against code: the private key is a PEM with `\n` escapes (not base64), and webhooks route under `/api/v1/webhooks/` |
| `docs/runbooks/private-beta-verification.md` | Reference to the deleted secure-private-beta spec replaced with ADR-010 |
| `infra/r2/r2-layout.md` | Artifact key layout corrected to `scan-artifacts/{organization_id}/{scan_id}/{scanner}/{file}` |
| `infra/render/render-blueprint.md` | Rewritten to match `render.yaml` (API, maintenance cron, dispatch cron; no worker/scheduler) |
| `infra/upstash/queue-design.md` | Rewritten to the per-organization stream design with code pointers |
| `apps/worker/README.md` | Scheduling marked deferred |
| `scripts/rehearse_rollback.sh` | Comment-only path update to the archived decision table; `bash -n` passes |

## Not changed

Application source, tests, migrations, lockfiles, generated contracts, CI, `render.yaml`, environment files, `.audit/`, ignored evidence logs under `docs/reviews/readiness-2026-09-30/`, Git branches, stashes and worktrees. Archived files keep their original content (except the October plan's tracker), so their internal relative links may point to former locations; the archive README says so.

## Findings recorded for follow-up

- The 2026-10-16 report's recovery snapshot `/tmp/scanforge-cleanup-20261016-6donpa6z` no longer exists; Git history is the only recovery path for that cleanup.
- The CI path filter still lists `scanforge-security-platform/spec/**`; harmless now that `spec/` is gone, but it can be removed in a CI change.
- Git housekeeping (19 stashes, stale branches, two prunable worktrees) and the nested `.github/` question are open items in the plan.

## Follow-on publication

The redirection was published as spec [#32](https://github.com/Fchery87/scanforge/issues/32) with 22 sub-issues (#33–#54) carrying native blocked-by links; the plan tracker maps tasks to issues.

## Validation

Recorded in the commit/PR for this change: active-document link check, `git diff --stat` review confirming only documentation and one script comment changed, and `bash -n scripts/rehearse_rollback.sh`.
