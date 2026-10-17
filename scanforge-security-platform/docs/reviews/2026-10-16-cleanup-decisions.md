# Project directory cleanup decisions

## Status

User accepted Q1–Q15 and confirmed the concrete [cleanup manifest](2026-10-16-cleanup-manifest.tsv) with “Looks good” on 2026-10-16. The authorized cleanup is complete; results and verification are recorded below.

## Accepted boundaries

- Q1: Clean the application directory; inspect parent Git-root dependencies, preserve the current nested layout and treat root restructuring separately.
- Q2: Remove reproducible build/test/analysis caches while initially retaining installed dependencies and virtual environments. Preserve environment/credential files. Inspect unfamiliar local-tool, recovery and worktree directories individually.
- Q3: Retain current setup/operations, glossary/accepted ADRs, one authoritative implementation plan, necessary evidence and unresolved requirements. Remove superseded working-tree documents only after preserving unique content and repairing references. Use Git history for obsolete tracked material rather than creating another archive. Retain the recent roadmap grilling record until its decisions/acceptance requirements are represented elsewhere.
- Q4: Inventory apparently unused code but delete only after reference/purpose analysis and focused verification. Preserve database migrations and required recovery tooling. Deferred product code requires an explicit removal decision.
- Q5: Create a concrete path/purpose/tracked-status/reference/removal/recovery manifest. Protect uncommitted work and unique local data. Validate links, commands, config and affected tests. Avoid blanket clean/deletion and uninspected worktree removal.

## Read-only inventory evidence

- Git root is the parent `scanforge`; executable CI is `../.github/workflows/ci.yml` and parent agent instructions reference this project's domain docs.
- Accepted ADR-010–017, October implementation plan and roadmap interview are untracked. CONTEXT.md, the September plan and apps/web/next-env.d.ts are modified. Preserve all before cleanup; do not absorb unrelated source changes into a documentation snapshot.
- Reproducible candidates: web .next approximately 405 MB, root mypy cache approximately 58 MB and API mypy cache approximately 57 MB, plus smaller lint/test caches. Sizes are inventory observations, not promised reclaimed disk.
- Preserve installed node_modules approximately 787 MB and Python environments approximately 304 MB/170 MB initially.
- Nested secure-private-beta worktree is clean but diverged: 13 branch-only commits and 67 main-only commits. Its roughly 1.3 GB checkout is separate from preserving its Git branch/history.
- Twenty-one missing /tmp worktree registrations are prunable; their branches are not thereby obsolete.
- .cache/scanforge-recovery is an unborn repository with no refs or Git objects. .apex-code has two small permission JSON files without located project references. Environment-owned protected entries remain untouched.
- .audit TSVs are tracked decision records. Ignored readiness evidence logs are unique evidence candidates, not generic disposable logs.
- packages/contracts contains only a future-placeholder README. No implementation consumer was located.
- apps/api/openapi.json and apps/web/lib/api-types.ts are generated but required by current generation/CI contracts.
- docs/README.md, spec/ROADMAP.md and older beta specifications conflict with the accepted October execution authority. Setup instructions overlap; September policy/decision records retain linked detail and receipts.

## Concrete accepted choices

### Round 2 Q6–Q11 acceptance

- Q6: Remove generated build/test/lint/type/bytecode/incremental caches after coordinating running development processes. Keep dependencies, virtual environments, editable-install metadata, lockfiles, generated API contracts and environment files.
- Q7: Retire the clean nested checkout only after preserving/verifying its branch and unique commits. Prune missing worktree registrations, never branches. No merge/reset/history deletion.
- Q8: Root README is navigation; retain one setup guide, one implementation architecture overview, CONTEXT glossary, all ADRs, October plan/grilling and needed runbooks. Merge unique instructions and correct stale authority indexes before deleting duplicates. Retain detailed September requirements/evidence until accounted; no new archive folder.
- Q9: Retain tracked audit trails and unique release evidence, explicitly inventory ignored evidence, and remove only identified duplicate/reproducible diagnostics. Inspect sensitive content before any log commit; no automatic raw-log staging.
- Q10: Remove placeholder packages/contracts and the empty unborn .cache/scanforge-recovery repository after rechecking. Preserve/ignore .apex-code local tool settings and protected environment entries. Retain nested GitHub automation configuration; root-level operational relocation is separate.
- Q11: Preserve deferred feature code/tests. Only demonstrated dead/duplicate implementation files can be deleted with specific reference analysis and verification.

### Execution guards and recovery

Nested checkout ref is `refs/heads/feature/secure-private-beta` at `45dea2c3fd6102b85104638face8a9f894510362`. Thirteen unique commits are reachable from that ref. Tracked/untracked status is clean; ignored-name inventory found no extra credentials/env/data outside generated directories. Recheck immediately before retirement. Recover with `git worktree add <path> feature/secure-private-beta` and reinstall dependencies. Use Git's worktree removal, not recursive deletion.

Recovery scratch contains no non-Git files, refs, HEAD commit or objects. Its removal explicitly supersedes only the October implementation plan's preservation note for this inspected scratch path. Preserve other .cache content and .apex-code.

Tracked historical documents have recoverable Git versions. Before removal, record the baseline commit/path and account for unique content. August historical claims are API 136 tests, worker 54 tests, web 21 files/78 tests and a disposable migration0017/18 rehearsal; task commits remained unchecked. These are dated unverified historical claims, not current release evidence.

### Round 3 Q12–Q15 acceptance

- Q12: RUNNING_LOCALLY.md is the sole setup guide. Merge verified database/storage/auth/migration/scanner/troubleshooting instructions from docs/development-setup.md, docs/neon-setup.md and docs/scanner-setup.md, then remove those duplicates. Correct obsolete shared-key and queue claims. Keep app READMEs unless independently demonstrated redundant.
- Q13: Remove superseded March archive, May roadmap/hardening/AI plans/reviews, August plans, VALIDATION_TASKS.md and docs/CODE_REVIEW.md after unique accounting/reference repairs. Preserve ADR-007 rationale/reconsideration criteria in that ADR. Historical counts remain unverified. Retire unaccepted speculative proposals rather than silently adding them to the October backlog. Retain September evidence/receipt/support records.
- Q14: Account for and remove nine duplicated legacy specs: API_OVERVIEW, DB_SCHEMA, PRD, RBAC, ROADMAP, SCANNER_PIPELINE, STACK, TASKS and SECURE_PRIVATE_BETA. Source/OpenAPI/migrations, accepted ADRs, current architecture and October plan provide their authorities. Preserve explicit JWT issuer/audience, coordinator credential exclusion, canonical GitHub origin, request-local audit, project audit filtering and worker audit actor acceptance requirements in the October plan. Retire unmeasured old timing/expansion promises. Retain detailed September evidence specs.
- Q15: CONTEXT becomes concise domain definitions and authority pointers after unique accepted policy is moved to ADRs/plan. SYSTEM_OVERVIEW remains the implementation architecture, separating current behavior/defects from accepted target. Root README absorbs navigation before duplicate docs/README and spec/README indexes are removed.

### Manifest and accounting

The manifest has 75 entries: 34 tracked file removals after prerequisites, 10 generated cache/build roots, 28 first-party bytecode directories, one empty recovery scratch repository, one worktree checkout, and one missing-registration pruning operation. Tracked deletion candidates are clean against `60621705b9307553430490aa364d778f503bfde2`, and their Git objects were checked. The manifest records each baseline Git path and SHA-256. Recheck before execution; changed candidates are preserved for review.

The 34 tracked removals comprise 19 historical plans/reviews, three duplicate setup guides, two duplicate indexes, nine legacy specs and one placeholder package README. No application source, migration, fixture, lockfile, generated API contract or active executable configuration is in that deletion set.

Accounting destinations:

| Candidate content | Retained destination / disposition |
| --- | --- |
| Setup commands and unique provider/scanner instructions | RUNNING_LOCALLY.md, verified against current commands/configuration; discard unsupported bypass and obsolete credentials guidance |
| Current runtime/module/provider facts and known gaps | docs/SYSTEM_OVERVIEW.md, source-backed and distinguished from target guarantees |
| Accepted policy duplicated in glossary/plans/specs | Existing appropriate ADR or October plan; CONTEXT keeps domain definitions/pointers |
| ADR-007 deferred GlitchTip rationale | Self-contained ADR-007 reconsideration trigger for Slack volume/grouping needs |
| August counts/migration claims | Dated unverified historical accounting above; no current pass credit |
| May/March completion claims without receipts | Retired historical claims recoverable from Git; not proof of completed October work |
| May speculative commercial/enrichment/product suggestions | Retired proposals, not accepted beta requirements |
| SECURE_PRIVATE_BETA explicit security constraints | October M02/M04/M06/M12 acceptance details and appropriate ADR pointers |
| Legacy API/schema/stack/registry inventories | OpenAPI, models/migrations, package/deployment configuration and executable registry; README points to them |
| September requirements/actual receipt references | Retain existing September files and R04/R12 support records with historical authority clearly labeled |

Keep commercial-launch privacy/support/subprocessor/trust-evidence prerequisites visible as later launch constraints; they are not newly approved beta features. Old 95%-within-five-minutes start, ten-minute recovery and numerical expansion claims are retired/unapproved pending measurement.

The approved generated/scratch/checkout roots were:

```text
.mypy_cache/
.pytest_cache/
.ruff_cache/
apps/api/.mypy_cache/
apps/api/.pytest_cache/
apps/api/.ruff_cache/
apps/worker/.pytest_cache/
apps/worker/.ruff_cache/
apps/web/.next/
apps/web/tsconfig.tsbuildinfo
.worktrees/secure-private-beta/
.cache/scanforge-recovery/
packages/contracts/README.md
```

Also remove only the `__pycache__` children of inspected first-party app, Alembic, test and script directories, excluding dependencies, worktrees and evidence. Empty parent directories may be removed only after their enumerated contents are removed. Removing packages/contracts does not require changing CI's historical packages path filters.

## Execution order and verification

1. Record current status, retain the baseline manifest, and preserve pre-edit changed/untracked documentation in a scoped recoverable snapshot. Do not stage unrelated source or credentials. Recheck active process conflicts before removing their caches.
2. Merge setup, architecture, navigation and unique accepted policy. Add preserved security acceptance detail to the October plan and make ADR-007 self-contained. Reconcile retained runbook/app README links without rewriting historical evidence as current proof.
3. Remove only manifest-listed tracked files after their accounting conditions pass. Repair active Markdown links and literal command/config references; historical provenance strings remain explicitly historical.
4. Remove only inspected generated caches and empty scratch state. Preserve node_modules, virtual environments, editable-package metadata, .env, .audit and ignored readiness evidence. Add local-tool/scratch ignore coverage without blanket-ignoring future evidence.
5. Recheck worktree cleanliness, ignored local-data inventory and preserved branch/commit reachability, then use Git worktree removal and dry-run-reviewed missing-registration pruning. If metadata permissions prevent these operations, leave them pending and report the exact limitation; do not substitute recursive deletion.
6. Verify active links, documented command paths, generated-contract consumers, preserved unique requirements, Git recoverability and unrelated file integrity. Focus runtime checks on any actual implementation change; documentation/cache removal alone does not establish or require claiming a passing release suite.
7. Record actual removed paths, retained exceptions, validation results and reclaimed size. Keep recovery evidence until cleanup review is complete. No broad branch/history deletion, dependency reinstall, root migration or production action is included.

## Final confirmation boundary

All cleanup policy questions identified by the inventory are settled. Final confirmation of this manifest closes the grilling session and authorizes the scoped cleanup. Conditions such as changed worktree state or unaccounted unique content are execution guards: preserve and report exceptions rather than expanding deletion scope.

## Execution results — 2026-10-16

- Removed exactly 34 approved tracked files: 33 superseded/duplicate documents and one placeholder package README. Consolidated setup into RUNNING_LOCALLY.md, navigation into README.md, implementation architecture into SYSTEM_OVERVIEW.md and definitions into CONTEXT.md. Preserved unique accepted requirements in the October plan and ADR-007.
- Removed 10 generated cache/build roots, 28 first-party bytecode directories and the inspected empty recovery scratch repository. Retired the clean secure-private-beta checkout using Git; retained its branch at `45dea2c3fd6102b85104638face8a9f894510362` and its 13 unique commits. Dry-run reviewed and pruned 21 missing worktree registrations; all branch refs were unchanged.
- Removed 1,669,266,642 bytes of inventoried file contents (about 1.67 GB decimal). This is a logical file-size total, not a measurement of physical disk space freed. No retained exceptions.
- Preserved application source, tests, migrations, lockfiles, generated API contracts, dependencies, virtual environments, local settings, credentials, protected environment entries and unique evidence. The existing next-env.d.ts modification matches its pre-cleanup hash. Two rehearsal scripts changed only documentation-path comments; executable lines are unchanged.
- Verification passed: local Markdown links in 47 retained files; exact tracked-deletion manifest match; all baseline implementation hashes except the two verified comment-only scripts; all 21 protected evidence hashes; retained dependency/config/contract existence; unchanged HEAD and branch refs; shell syntax for both rehearsal scripts; `git diff --check`.
- Setup instructions were checked against source; no runtime suite or live setup was run. This cleanup provides no new application readiness or release-pass evidence.
- Pre-edit recovery snapshot: `/tmp/scanforge-cleanup-20261016-6donpa6z/documents-before.tar.gz`. The same private directory retains baseline hashes, execution journal and empty exception list. Keep it through cleanup review; obsolete tracked files also remain recoverable from the manifest's baseline Git commit. The snapshot excludes credentials.
