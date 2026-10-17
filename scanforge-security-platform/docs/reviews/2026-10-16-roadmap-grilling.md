# Roadmap grilling decision record

## Status

Confirmed. User accepted Q1–Q54 across all nine rounds and confirmed the consolidated shared understanding with "Looks good" on 2026-10-16. The cross-decision audit's seven refinements are accepted and incorporated. No source fixes or deployment actions were performed in this interview. The subsequent [implementation plan](../plans/2026-10-16-managed-beta-implementation-plan.md) translates the accepted baseline into execution tasks.

Final independent document consistency review found no material unresolved contradiction. Local link targets, whitespace, and disposition coverage for all 25 original findings were checked. These are documentation checks only; implementation and release evidence remain outstanding.

## Accepted decisions

Round 1 Q1–Q5 are recorded in [ADR-010](../adr/ADR-010-managed-beta-release-scope.md). Domain terms are recorded in [CONTEXT.md](../../CONTEXT.md).

### Round 2 Q6–Q11

- Q6: All seven registered scanners must execute real analysis and pass known-positive and valid-empty fixtures inside the released image. An unready scanner must be explicitly removed from advertised and expected coverage. Version output never counts as analysis.
- Q7: Persist valid findings with explicit partial coverage when some scanner outcomes fail. Distinguish missing, failed, timed-out, and invalid-output outcomes. Partial scans cannot authorize absence transitions or a clean verdict.
- Q8: Retain only detector identity, classification, verified repository/revision, path and line range for secret findings. Exclude secret values, sensitive matches, decoded values and secret-bearing snippets from durable/external boundaries. Normalize safe evidence before discarding raw data. Use location/detector identity rather than credential-derived fingerprints for beta; moving a secret may create a new finding.
- Q9: Host-service coordinator on a dedicated Linux VM with a local container runtime, as recorded in [ADR-011](../adr/ADR-011-beta-executor-and-github-ingress.md).
- Q10: Initial release requires GitHub/repository onboarding, manual full and automatic push scans, evidence/history/manual triage, assignment/due dates, audit and accurate coverage, and unresolved exposure counts. Hide AI, PR diff review/Checks/comments, automated suppression, custom scheduling/on_push schedule objects, exports, letter grades and enforcement until verified. Daily/weekly schedules follow as a later beta increment unless a design-partner requirement is explicitly accepted. Secure or disable deferred endpoints as well as their UI.
- Q11: One signature-verified GitHub App ingress, immutable repository and installation routing, verified installation-user access, and removal-event revocation, as recorded in ADR-011.

Required evidence includes positive/empty/invalid output fixtures for each shipped scanner, secret canaries across every durable/external boundary, partial results without closure/clean verdict, and a host-based scan with correct mounts/permissions/cleanup. GitHub acceptance must cover authorized connection and revoked installation/repository access. These are test requirements, not passing results.

### Round 3 Q12–Q17 acceptance

Repository ownership, automatic default-branch scope, immutable scan identity, repository/ref changes, two-observation closure, and human triage precedence are accepted in [ADR-012](../adr/ADR-012-repository-authority-and-ordered-evidence.md). Required scenarios include unauthorized/duplicate binding, rename versus transfer, branch movement while queued, inaccessible exact SHA, force push/recreation, default/manual branch overlap, same-commit reruns, delayed presence, scanner upgrade incompatibility, human/machine races, risk expiry, duplicate cycles, stale revisions, and atomic bulk rollback. These remain acceptance requirements, not verified outcomes.

### Round 4 Q18–Q23 acceptance

Durable dispatch, classified retries, fenced execution, terminal cleanup, artifact/structured-evidence retention, and transactional audit are accepted in [ADR-013](../adr/ADR-013-durable-delivery-and-terminal-evidence.md). Three execution attempts, 120-second leases, and 30-second renewals remain candidate operational values. Required scenarios include database commit followed by queue outage, duplicate delivery, manual idempotency versus intentional rerun, lost completion response, post-completion notification failure, stale/disabled worker mutations, unreachable old host, both cancellation/completion lock orders, crash during cleanup, artifact substitution/overwrite/expiry, and audit-write rollback. No passing execution evidence is implied.

### Round 5 Q24–Q29 acceptance

- Q24–Q27: Category-specific versioned identity, explicit cross-scanner equivalence, severity/remediation provenance, seven-day database freshness, upgrade baselines, and conservative legacy migration are accepted in [ADR-014](../adr/ADR-014-finding-identity-and-provenance.md).
- Q28: Unresolved counts include open/reviewing/to_fix/not_observed. Accepted risk and false positives are separate; duplicates count through their canonical target. Coverage, disposition and historical observations remain distinct. Zero findings with missing/stale coverage means unknown. Initial prioritization uses visible severity, importance and age; numeric risk scores remain hidden until formula/recalculation/interpretation are validated. Letter grades remain deferred.
- Q29: Versioned API response contracts are authoritative. Generate client types/runtime validators where practical; handwritten validators must accept real endpoint responses. Distinguish loading/empty/unavailable/stale/partial/expired states. UI capability hints do not replace server authorization. Test assembled routes and authenticated browser flows, including nullable integration, pagination, trends and downloads. Secure or disable deferred endpoints.

Required scenarios include alias equivalence and non-equivalence, moved code without disposition transfer, conflicting scanner severity/fixes, stale/unverifiable databases, upgrade-induced disappearance, repeatable legacy reconciliation, every unresolved status in counts, unscanned repositories, and real endpoint-to-client/browser contract checks. These remain requirements, not passing results.

### Round 6 Q30–Q35 acceptance

- Q30–Q33: Organization-wide access matrix, service-level revocation, verified invitations, disconnect/archive/erase distinctions, retired-branch reconciliation, and 30-day maximum backup retention are accepted in [ADR-015](../adr/ADR-015-beta-access-and-data-erasure.md). Infrastructure enforcement of backup retention remains unverified.
- Q34: Bound clone/checkout size and files, scanner concurrency, memory/process/disk/output/time, completion payloads and pending work. Reject unsupported work explicitly or preserve valid resource-limited partial results. Never truncate into clean success. Schedule scanners against measured capacity. September payload bounds remain candidates; approve actual host/provider/cost/limits after representative and maximum-envelope measurements. No infrastructure purchase is authorized by this design acceptance.
- Q35: Require named primary and backup operators before onboarding. Business-hours managed beta, with automatic containment outside support hours and no unmeasured numerical availability/24-hour response promise. Safe alerts cover cleanup, lost authority with unresolved execution, dead letters, sustained backlog, stale assets, dispatch, audit and storage failures. Rehearse tenant stop, credential rotation, host fencing, queue recovery and rollback. Operator identities remain an onboarding gate, not an invented assignment.

Required evidence includes all role/resource combinations, disabled users with valid tokens, membership/worker revocation, owner transfer races, unverified email rejection, disconnect versus archive versus erase, late delivery after deletion, backup restore with tombstones, bounded hostile output/disk, and operator drill/alert receipts. These remain requirements, not results.

### Round 7 Q36–Q41 acceptance

- Q36–Q37: Versioned producer cutover, tested migration/rollback, tenant pilot and GitHub reconciliation are accepted in [ADR-016](../adr/ADR-016-versioned-cutover-and-provider-reconciliation.md).
- Q38: Deferred schedules initially provide daily/weekly full scans at explicit UTC time/weekday with UTC/local next-run display. Unique occurrence and atomic dispatch prevent duplicates. Updates recalculate next run; disabling stops future occurrences. After downtime dispatch at most one catch-up scan at current verified revision and record skipped occurrences. Push triggers are separate settings. Custom cron remains deferred. Acceptance covers concurrency, clock boundaries, downtime, settings and access removal.
- Q39: Deferred rules suppress presentation/notifications, not observations or human disposition. Retain appropriately labeled exposure totals. Start with repository-scoped detector/advisory and normalized-path matching. Require reason, approver, expiry, affected-findings preview and audit; reject ambiguous/cross-tenant criteria. Expiry/disable restores visibility without rewriting history. Broad organization rules require another review. Acceptance covers matching boundaries, previews, expiry, overlapping rules, authorized scope and preserved evidence.
- Q40: Deferred exports start with CSV/JSON authorized snapshot data: filters, snapshot time/version, row count, schema version, requester, checksum and expiry. Durable pending/running/completed/failed/expired states; reauthorize generation and download; enforce redaction, CSV formula neutralization, authenticated downloads and artifact ownership. PDF/pipeline/narrative reports remain deferred pending specification. Acceptance covers concurrent edits, revocation, large/interrupted exports, injection and secret canaries.
- Q41: Deferred PR security review uses verified head/base identities, authorized fork access and documented merge-base comparison. Separate introduced from pre-existing findings. Anchor only verified changed lines, otherwise summarize. Persist publication identities, reconcile retries, label superseded reviews and preserve discussion. Incomplete coverage is neutral/visible, never clean. Advisory initially; blocking enforcement and general AI bugs require separate gates. Acceptance covers multi-commit/rebase/force-push/rename/delete/fork, duplicate/lost publication and partial coverage.

These are future enablement contracts, not expansion of the initial beta or passing execution results.

### Round 8 Q42–Q47 acceptance

- Q42–Q45: Server-derived atomic completion, canonical sanitized digest/replay, receipt-read recovery, separate AI capabilities, consent and untrusted-content boundaries, independent annotation jobs and versioned tenant caches are accepted in [ADR-017](../adr/ADR-017-authoritative-evidence-and-optional-ai.md).
- Q46: Evaluate explanations/detection separately on versioned held-out cases including clean/buggy/adversarial/duplicate/unsupported inputs. Starting detection gates: at least 100 representative PR cases with at least 50 clean and 50 containing adjudicated supported defects; precision >=90%, recall >=80% for declared classes, with class/repository/language/severity breakdowns and no aggregate concealment of weak advertised classes. Freeze protocol before measuring; account explicitly for abstentions, duplicates and missing context. Human-adjudicate evidence/remediation quality. Require approved measured latency/cost envelope and shadow mode before visible publication. Passing results do not generalize to every repository. Thresholds are accepted enablement targets, not observed performance; corpus representativeness and operating envelope require evidence.
- Q47: A release dossier identifies deployed revisions/digests and proves scanner positive/empty/invalid/timeout/stale cases; all roles/tenants/revocation/install authority; dispatch/replay/stale-attempt/terminal races; cleanup/crash/fencing/redaction/artifact/download; migration/contracts/browser/partial states; measured limits/alerts/restore/tombstones/rollback. Required integrations cannot pass by skipping. Gate commands/environments must resolve real tests/services. Every original finding links disposition and acceptance evidence. Deferred capabilities are unavailable in UI and unauthorized backend execution. Limitations must fit accepted beta scope.

Acceptance must also exercise canonical-equivalent and conflicting payloads, duplicate keys, unknown fields, forged worker summaries, replacement receipt-read versus write, AI consent revocation/provider changes/cache isolation, malicious source instructions, budget exhaustion and AI failure after scan completion. No implementation or quality result is claimed.

## Evidence boundaries

### Round 9 Q48–Q54 acceptance

- Q48: Independent ephemeral exact-revision context acquisition for future AI; current access checks, separate cleanup and explicit skip when unavailable. Incorporated in ADR-017.
- Q49: Branch-scoped manual fixes with reason/evidence; unresolved other obligations retain exposure. Explicit global scope for accepted-risk/false-positive judgments. Incorporated in ADR-012.
- Q50: Exact dependency identities plus verified advisory lineage and manifest/path occurrences; vulnerable upgrades preserve exposure and do not inherit human dispositions. Incorporated in ADR-014.
- Q51: Duplicate groups aggregate every member's presence/branch obligations, count once and remain unresolved when any member does. Audited cycle-free target changes preserve history and review dispositions. Incorporated in ADR-012.
- Q52: Latest-state automatic coverage permits explicit supersession of unstarted work by newer descendants in the same generation. Preserve trigger/scan/skipped records, never coalesce manual requests silently or supersede running work implicitly. Capacity rejection precedes manual acceptance. Incorporated in ADR-013.
- Q53: Accept low-activity automatic-closure limits; expose missing evidence and permit evidence-backed human resolution without weakening freshness or counting reruns. Incorporated in ADR-012.
- Q54: Verify immutable objects before atomically publishing references/receipt; inaccessible orphan cleanup; preserve valid structured findings with explicit unavailable secondary artifacts. Essential validating evidence must exist. Incorporated in ADR-013.

Required scenarios include AI acquisition after scan cleanup/revocation, main fixed with release still present, vulnerable version upgrades, duplicate target fixed/deleted while member persists, burst pushes/manual capacity/force-push boundaries, slow repositories across database refresh, and object upload success followed by transaction failure. These are acceptance requirements, not passing results.

### Review evidence boundary

The source review's findings are inputs to design, not proof of a deployed incident. Follow-up source checks support B1–B12. Existing completion claims in earlier plans must be reconciled with code and execution receipts. The [September decision table](../../spec/2026-09-13-scan-evidence-decisions.md) contains proposed semantics and an open G1 measurement gate; ADR-010 does not accept that table wholesale.

## Coverage frontier

### Cross-decision audit frontier

All seven audit refinements are resolved by accepted Q48–Q54. No additional product decision is currently identified in the reviewed scope. The execution and enablement gates below remain explicitly unverified; this is not a claim of exhaustive future bug discovery.

| Branch | Review findings | Decision status |
| --- | --- | --- |
| Product scope, cohort, hosting, feature deferral, release evidence | Round 1 Q1–Q5 | Accepted in ADR-010 |
| Scanner coverage, output validity, secrets, artifacts | B1–B4, S7 | Execution/secret/artifact/identity/provenance semantics accepted; resource limits and fixtures open |
| Exact revisions, PR comparisons, ordering and lifecycle | B5, S5 | Ordered evidence/migration/retirement accepted; deferred PR comparison contract accepted in Q41 |
| GitHub onboarding, triggers and developer feedback | B6–B7, S1, P2 | Ingress/ownership/revocation/dispatch/reconciliation accepted; deferred feedback contract accepted |
| Frontend contracts, exports and trend routing | B8–B9, B11 | Q29 accepted; exports deferred with Q40 enablement contract; implementation/evidence required |
| Suppression rules and scheduling | B10, B12 | Deferred/hidden; Q38–Q39 enablement contracts accepted |
| Resource authorization, audit and artifact ownership | S2–S4 | Matrix/revocation/audit/artifact/erasure semantics accepted; evidence and enforcement required |
| Execution topology, cancellation and resource limits | B3, S6 | Topology/fencing/cancellation/bounding policy accepted; actual limits/timing measurements open |
| Scoring and exposure semantics | S8 | Q28 accepted; grades/numeric score deferred; transparent unresolved counts required |
| Release gates, capacity, migration and recovery | S9 | Q47 dossier accepted; actual measurements, operator assignments and execution receipts outstanding |
| AI capability, consent, cache, budgets and quality evaluation | P1, P3–P4 | Initial AI disabled; Q43–Q46 future enablement contract accepted; evidence outstanding |

Each branch must end with a disposition, acceptance scenarios, dependencies, and any unresolved measurement requirement. A decision is not an implemented or verified fix.

## Original finding dispositions

All rows remain unimplemented/unverified in this interview. Fix means required before enabling the affected beta workflow. Deferred means unavailable until its accepted enablement contract passes; secure or disable associated endpoints now.

| Finding | Disposition | Accepted decisions | Required acceptance evidence |
| --- | --- | --- | --- |
| B1 Contained version-only scanners | Fix | Q6–Q7, Q26, Q34 | Real image execution, positive/empty/invalid fixtures for every shipped scanner |
| B2 Secret evidence loss/corruption | Fix | Q8, Q24, Q42 | End-to-end preserved redacted findings, idempotent sanitization, canaries across boundaries |
| B3 Unrunnable beta deployment | Replace topology | Q9, Q20, Q34–Q36 | Host coordinator with actual daemon/mount/ownership, measured containment and pilot |
| B4 Deleted output before upload | Fix | Q21–Q22, Q54 | Artifact lifetime through persistence and cleanup, upload/transaction failure recovery |
| B5 Wrong revision and PR diff | Exact revision fix; PR diff deferred | Q13–Q16, Q41 | Queued branch movement/exact SHA tests; later multi-commit/merge-base/fork fixtures |
| B6 Onboarding/webhook/enqueue gaps | Fix | Q11–Q14, Q18, Q37, Q52 | Verified installation/repository binding, default-branch event to durable scan and reconciliation |
| B7 Missing GitHub publication | Defer | Q10, Q41 | Revision-bound advisory publication, idempotent retries and superseded review handling |
| B8 Client/API response mismatch | Fix used contracts; disable deferred paths | Q29, Q47 | Actual responses through validators and authenticated browser workflows |
| B9 Exports broken/incomplete | Defer | Q10, Q40 | Snapshot CSV/JSON generation, safe download, revocation, expiry and injection/redaction cases |
| B10 Suppression rules inert | Defer | Q10, Q39 | Scoped matching/preview/expiry with preserved observations/dispositions and counts |
| B11 Shadowed trend route | Fix if exposed; otherwise disable | Q29, Q47 | Assembled router request plus honest chart/browser behavior |
| B12 Scheduling incomplete | Defer | Q10, Q38 | Atomic occurrences, UTC recurrence/update/downtime/concurrent scheduler tests |
| S1 Installation ownership | Fix | Q11–Q12, Q31, Q37 | Ownership verification, unverified/foreign binding denial and revocation |
| S2 Mutation before scope check | Fix | Q17, Q23, Q30–Q31, Q42 | Service/route role-and-scope matrix, no writes on denial, bulk rollback |
| S3 Audit misses mutations | Fix | Q23, Q47 | Transactional event persistence and mutation rollback on audit failure |
| S4 Artifact ownership signing | Fix | Q22, Q31, Q54 | Foreign-key denial, current authorization and verified immutable references |
| S5 Unverified temporal closure | Fix | Q14–Q17, Q20, Q24–Q27, Q42, Q49–Q53 | PostgreSQL races, ordered branch/generation evidence, legacy and duplicate/upgrade cases |
| S6 Incomplete containment/limits | Fix | Q9, Q20–Q21, Q34–Q35 | Production-mode containment, process/container stop, hostile bounded output/disk and fencing |
| S7 Artifact/provenance overwritten | Fix | Q22, Q26, Q42, Q54 | Runtime manifest, preserved references, canonical replay and object availability |
| S8 Misleading scoring | Fix exposure counts; defer scores/grades | Q10, Q17, Q28, Q49–Q53 | All unresolved states, unknown/stale coverage, duplicate groups and vulnerable upgrades |
| S9 Nominal release gates | Fix | Q5, Q34–Q36, Q47 | Existing integration paths/services, no skipped required tests, measured release dossier |
| P1 AI explanation versus detection | Defer distinct capabilities | Q10, Q43–Q46, Q48 | Separate explanation/detection evaluation and source/consent boundary receipts |
| P2 Incomplete developer review loop | Defer | Q10, Q41, Q44 | PR revision/publication/discussion reconciliation; mutations require later authorization |
| P3 AI cache/budget/coupling | Defer | Q43–Q45, Q48 | Independent jobs, versioned tenant cache, revocation and budget/error isolation |
| P4 No demonstrated review quality | Defer claims/enablement | Q46–Q47 | Frozen held-out protocol, measured targets, human adjudication and shadow evaluation |

## Outstanding execution and enablement gates

These are prerequisites to implementation rollout or future feature enablement, not silently assumed decisions:

| Gate | Required concrete result |
| --- | --- |
| Operating envelope | Representative sanitized repositories/payloads, maximum limits and overflow results, chosen host/provider, concurrency, memory/disk/time and p95 measurements; explicit approval of final envelope/cost |
| Recovery parameters | Measure and approve lease/renewal/reclaim/cleanup/retry/reconciliation/staging intervals; three attempts, 120-second lease and 30-second renewal remain candidates |
| Operator readiness | Named primary/backup, support boundary, alert destinations and witnessed drill results before onboarding |
| Storage/erasure | Demonstrate immutability/access/redaction, 90-day sanitized artifact expiry, maximum 30-day backups, tombstone-aware restore and verified erasure |
| Migration/cutover | Enumerated legacy reconciliation, supported contract matrix, drained old attempts, backup/restore/rollback results and test-tenant/partner pilot |
| Initial beta release | Q47 dossier tied to actual source/schema/worker/image identities; every enabled finding disposition linked to passing evidence |
| Deferred features | Q38–Q41 and Q43–Q46 contracts pass before exposure; broader features such as PDF/custom cron/blocking enforcement/customer runners require separate design |
| AI evaluation | Adjudicated representative held-out corpus, declared supported classes, fixed metrics protocol, measured quality/latency/cost and consent/provider handling before shadow/visible enablement |

Numeric operating parameters are settled by measured proposals, not guessed from hosting labels. Missing measurements are work to perform. Acceptance targets such as seven-day database freshness, 90-day artifact expiry, 30-day backup maximum and AI quality thresholds are policies to implement and prove, not current measured capabilities.

## Implementation dependency outline

1. Establish versioned domain contracts, authoritative resource access and audit transactions; disable unsafe/deferred surfaces.
2. Implement host executor, scanner commands/parsers/redaction/provenance and bounded cleanup; verify real positive/empty fixtures.
3. Implement immutable scan identity, durable dispatch, fenced attempts, atomic completion, object references and recovery.
4. Implement ordered branch observations, human dispositions, deduplication/lineage and conservative legacy migration.
5. Finish GitHub ingress/reconciliation and the required onboarding/triage/coverage UI as complete vertical workflows.
6. Measure capacity, rehearse recovery/erasure/migration/rollback and satisfy the release dossier before a staged beta.
7. Enable deferred schedules/suppression/exports/PR review only through their acceptance contracts; enable AI through independent consent/evaluation gates.

This outline is a dependency guide for a subsequent executable plan, not an implementation completion claim or an infrastructure spending authorization.
