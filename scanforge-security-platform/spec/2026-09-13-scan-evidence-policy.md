# Scan evidence and lifecycle policy v1

**Status:** Decision closure draft. Semantic choices below are settled for R03 review; payload capacity approval remains a human gate. Not an Accepted ADR or runtime readiness claim.

**Date:** 2026-09-13

**Baseline:** `549dc87`. Amends the proposed policy from `0d7b50b` without adopting its tracker changes.

## Scope and ownership

The API owns execution authority, completion, comparison, and finding transitions. Workers report observations, not lifecycle truth. Extend Scan, ScannerRun, FindingInstance, and FindingEvent. Do not create a parallel evidence store. ADR-002, ADR-003, ADR-004, and ADR-009 remain in force.

The [decision table](2026-09-13-scan-evidence-decisions.md) assigns implementation owners, migration work, and acceptance tests. These are role owners, not claims that a named person has approved a deployment. R03 remains in progress until its explicit human gate and independent review close. R04, R05, and R09 still require real integration evidence. AI stays disabled, GitHub feedback stays advisory, and this document authorizes no merge, deployment, onboarding, or production data changes.

## Version and authoritative records

Require integer `contract_version = 1`. Reject absent, unknown, and unsupported versions with HTTP 422 `unsupported_contract_version`, before evidence mutation. Publish supported versions in execution context. No automatic downgrade. Drain existing attempts before coordinated API/worker rollout; explicitly restart unfinished legacy scans under new attempts. Historical completed scans remain readable as `legacy_unknown` and never acquire invented provenance.

The API persists immutable organization/project/repository associations, ref identity, base/head, resolved commit, scan type, expected scanner set, normalized path configuration, and execution revision before granting execution. Workers must match this context. For a branch request, the trusted API GitHub adapter resolves its head before execution; the coordinator verifies checkout matches that SHA. Scanner observations carry binary version, parser version, rules digest, database digest and build time where applicable, image digest, exact scope, outcome, sanitized findings, and artifact descriptors. The API derives fingerprints, counts, health, and comparison results. Caller summary fields have no authoritative counterpart in v1; reject them rather than silently accepting contradictory input.

One validated terminal outcome is required for each expected scanner. Reject unknown names, duplicates, omitted outcomes, findings attributed to an unexpected scanner, scope violations, and inconsistent commits with HTTP 422. An expected scanner that never ran must have explicit `missing` and a reason. Scanner outcomes are `succeeded`, `failed`, `timed_out`, `missing`, `skipped`, and `parse_failed`. Nonzero tool exit codes may mean findings for a documented adapter; exit zero alone never proves successful parsing. Only a supported parser accepting a complete schema may produce successful empty output. Failed or truncated output may be retained only as sanitized diagnostic artifacts, not accepted canonical findings.

### Stored health and projections

Keep orchestration `status` separate from `scanner_completeness` and per-finding `lifecycle_eligibility`. Persist all three in the completion receipt and expose them in API responses. ScannerRun stores its own outcome independently of ScanStatus.

| Field | Values and meaning |
| --- | --- |
| `status` | `queued`, `running`, `completed`, `failed`, `canceled`; `completed` means validated evidence committed, including explicit failed scanner outcomes |
| `scanner_completeness` | `pending` before completion; `complete` only when every nonempty expected scanner set member succeeded; `partial` for any other accepted terminal set; `unknown` for legacy rows |
| `lifecycle_eligibility` | Per finding/ref: `eligible` or `ineligible` plus ordered reason codes; scan summary: `not_evaluated`, `ineligible`, `mixed`, or `eligible` derived from those receipts, never a caller boolean |
| UI | Show `Completed · complete scanner coverage`, `Completed · partial scanner coverage`, `Failed`, or cancellation cleanup state. Show `No findings reported` rather than `Clean`; zero findings with partial health is not assurance |
| GitHub Check | While active: queued/in_progress; terminal: completed. Conclusion `neutral` for completed advisory results including policy violations and partial health; `failure` for orchestration failure; `cancelled` for cancellation. Title names partial coverage and cleanup pending where applicable. Never configure as a required merge gate |

Partial health blocks all absence observations for that scan. Dependencies, secrets, and diff scans can record presence but cannot authorize automatic absence in v1. A full scan requires the API's full expected set, not a reduced worker-selected set.

## Repository, ref, and ordering identity

Repository comparison key is `(organization_id, project_id, repository_id, provider=github, external_repo_id)`. `external_repo_id` is GitHub's immutable repository ID verified through the installation. Display owner/name and clone URL are not identity. Rename within the same association preserves evidence after reauthorization. Transfer, installation loss, or project/organization reassignment suspends execution until access is reverified and starts a new comparison baseline. Never carry authority across tenants. Missing external IDs are legacy unknown. Forks remain different repositories even with shared commits.

Persist `ref_type`, full `ref_name`, and API-issued `ref_generation`. Only `branch` with exact case-sensitive `refs/heads/<name>` permits absence. Tags, detached SHAs, and pull-request refs remain presence-only. A PR records both approved base and head and does not impersonate its target branch. Default-branch changes select a different ref identity; they never move old history.

The API GitHub adapter records a dated ancestry receipt for each comparison: repository ID, older SHA, newer SHA, relationship, and provider response digest. GitHub compare must establish that older is an ancestor of newer. Accept `ahead` for a strict descendant and `identical` for equal SHA; deny `behind`, `diverged`, missing commits, unavailable API, or ambiguous/truncated comparison. Do not infer ancestry from timestamps, SHA ordering, a worker boolean, or changed-file lists. Merge commits qualify when the older commit is reachable through any parent, not just the first parent. The API must verify the resolved commit was reachable from the approved ref at resolution time.

A verified non-descendant ref update, deletion/recreation event, identity reassignment, or uncertain ref continuity retires the comparison baseline. Store a new baseline ID and generation in repository execution configuration; link its first full evidence scan and reset per-finding absence counters through audited FindingEvents. Do not erase observations or close old findings. A missed webhook cannot prove deletion never happened. If provider reconciliation cannot establish continuity after an outage, reset conservatively. Observed deletion/recreation resets even when the SHA is unchanged. Late scans from a retired generation remain historical evidence only.

FindingInstance and FindingEvent retain ref generation and comparison baseline. Repository-scoped canonical fingerprints stay unchanged. Ref-specific observation state is separate from a human disposition. The repository-level finding may become `not_observed` or `fixed` automatically only when every non-retired tracked branch baseline where it was seen reaches that state. Unknown legacy branch evidence blocks repository-level auto-closure until reviewed. Retiring a branch does not count as absence; a reviewer must explicitly retire its unresolved finding obligation with reason and event. The UI/export must not label branch-local absence as fixed everywhere.

## Comparison and two-observation threshold

Use policy `scan-evidence-v1`, with threshold exactly two. There is no beta per-tenant threshold knob. Each qualifying absence must have a distinct scan ID and a distinct commit SHA, be a strict descendant of the last counted absence and the latest relevant presence, share the same ref generation/baseline, and cover the finding's full relevant scope with compatible provenance. If paths or prior provenance are unknown, deny. Deleted files count as covered only under a verified full scope that would include the old path if it existed. A full scan at a new descendant with no changes to the relevant path still counts. A rerun at the same SHA never counts again, even under a new scan ID or image.

The first qualifying absence records `not_observed`; the second records `fixed` with both scan IDs, commits, and policy version. Store per-ref observation history even when human state prevents the automatic transition. Partial, diff, and incomparable scans neither increment nor erase qualifying counters. Presence resets counters. A rules/baseline change starts a new series; old counters cannot be combined across policy domains.

Use commit ancestry, not completion arrival order, for automated state. Lock the relevant finding/ref history while applying it. Earlier or unrelated completion cannot undo a newer presence or absence on that ref. Presence from a diff scan is valid positive evidence and resets absence at its commit; lack of diff output is not negative evidence. For equal commits, presence dominates absence. Conflicting presence at the same commit revokes that commit's absence contribution and conservatively reopens eligible machine states. A late intermediate presence invalidates an absence pair that straddles it; recompute from retained ordered receipts, never increment a bare delivery counter. A later absence cannot close a finding seen at a newer commit on another unresolved tracked ref.

### Scanner and database compatibility

For absence, require exact scanner identity, binary version, parser version, rules digest, normalized configuration/path digest, and pinned image digest initially. Database-free tools explicitly record `not_applicable`, not null. A database-backed run requires digest, source, build timestamp, and a trusted image manifest. Database age must be at most seven days at execution start; a future timestamp beyond five minutes of server time is invalid provenance. A stale or unknown database permits observed findings but is ineligible for absence. This is a conservative beta policy choice, not a measured vulnerability coverage guarantee.

Identical database digests can compare if both observations met freshness rules. Changed database or tooling versions are incompatible by default. The v1 compatibility allowlist starts empty. A later versioned allowlist entry must name exact source/destination provenance tuples, scanner/advisory family, scope, fixture receipt SHA, and reviewer approval. Test removals, aliases, withdrawn advisories, package matching, rule disablement, and parser output changes; version ordering alone is insufficient. Apply entries prospectively and never retroactively recalculate closed history. Keep updating secure images. An incompatible update starts a baseline with presence evidence; it does not require retaining old vulnerable tooling or falsely closing previous findings. Manual verified remediation remains available.

## Attempt authority and reclaim

The API is the only issuer, renewer, revoker, and replacer of execution authority. Use a server-generated UUID attempt ID, monotonically increasing execution revision, verified worker principal ID, and database lease timestamps on Scan plus retained attempt audit metadata. No new bearer attempt secret: the existing revocable worker credential authenticates the caller, and attempt ID/revision are non-secret fencing identifiers. Bind authority to a coordinator incarnation ID as well as worker identity. Lost process state gets a new incarnation and must reclaim, not impersonate the old attempt.

Acquire/renew/reclaim transactions lock the Scan row and verify current worker status, organization, capability, terminal decision, and database time. Candidate operational defaults are a 120-second lease and renewal every 30 seconds. These are tunable, not empirically proven timings. They leave three missed renewal intervals before the deadline, but R09 must measure heartbeat latency, Redis pending visibility, long scanner runs, API outages, and process cleanup before enabling them. Approval must record the tested timings and amend this policy if they change. An expired lease cannot be renewed. Redis ownership is a delivery fact, not execution authority. Reclaim is eligible after a 120-second pending idle threshold, but the API grants a successor only after the current database lease expires or an authorized operator revokes it. A live lease wins against a new claimant even if Redis already reassigned the pending entry. The new claimant retains pending recovery state and does not start scanners or acknowledge. Use bounded retry; do not extend execution from Redis activity.

A coordinator that cannot renew must stop its containers by the lease deadline. A successor receives fencing authority but may not start scanners until previous-host cleanup is verified or that host is fenced off by the operator. Database lease expiry is not proof that a native process died. Record cleanup evidence and alert if host fencing is unavailable. A delayed heartbeat, progress request, artifact finalization, or completion from the old revision returns HTTP 409 `stale_attempt`. If a completion locks first while its lease is valid, it commits and reclaim sees terminal success. If reclaim locks first after expiry, old completion loses. Use database time at locked authorization check; transactions must be short and bounded.

Presign only organization/scan/attempt-specific exact artifact keys. Presigned staging writes are not authoritative. Finalization validates current attempt, object ownership, size, checksum, sanitized content type, and scanner association. Finalized bytes must be immutable: use an API-owned immutable destination or verified object version not writable by a surviving upload URL. Completion links only finalized objects for the accepted attempt. Stale staged objects cannot overwrite accepted evidence and are garbage-collected after 24 hours when no active attempt references them.

## Atomic completion and replay

Before commit, lock Scan, verify current authority and lease, verify artifact finalization receipts, then lock finding/ref histories in stable ID order. Persist scanner runs, canonical findings, instances, references, transitions, derived summary, terminal receipt and digest, and `completed` in one PostgreSQL transaction. Rollback leaves no authoritative partial evidence. Staging uploads may remain for recovery/garbage collection. Publish notifications and GitHub projections only after commit through retryable receipt-linked delivery. Projection failure must never turn a completed scan into failed.

Digest algorithm is SHA-256 over RFC 8785 canonical JSON of the validated, sanitized v1 evidence DTO. The DTO includes contract/policy versions, immutable scan context, attempt/revision, sorted scanner outcomes and provenance, scope, worker-reported execution timestamps/durations/exit codes, accepted canonical candidate content with instances/references, and finalized artifact key/version/size/content digest. Sort scanners by name; candidates by canonical fingerprint then occurrence identity and canonical bytes; references/artifacts/path sets by canonical bytes. Reject duplicate object keys, non-finite numbers, invalid Unicode, and unknown fields. Normalize defaults and UTC timestamps at validation; preserve string content otherwise. Exclude authorization headers, presigned URLs, request IDs, queue delivery IDs, retries, API receipt time, and API-derived summary/fingerprints/counts. Server recomputes fingerprints before hashing accepted candidates. Do not hash unsanitized secret values.

Persist the original response including inserted/updated counts, scanner counts, health, terminal status, and receipt ID. Identical authorized completion replay returns HTTP 200 with that exact stored business response, not zeroed counts or a fresh summary. If replay indication is useful, put it in a response header outside the stored business result. Different valid canonical evidence returns HTTP 409 `completion_payload_conflict` without mutation. Validation errors remain 422; oversize requests remain 413 even on replay.

For replay, the winning historical attempt may retrieve its receipt after its lease expires, but only while its worker principal remains enabled, authorized for this organization, and presents the winning attempt/revision. Superseded non-winning attempts cannot submit completion. A rotated credential for the same enabled principal can retrieve the receipt. A replacement worker with explicit receipt-read/recovery capability may GET the receipt without being allowed to replay another attempt's completion body. A disabled worker is denied even for identical replay. Receipt lookup never starts scanner work or grants mutation authority.

Retain completion/cancellation receipts, digests, attempt identity, and comparison/transition evidence for the lifetime of the retained scan/finding, with no automatic beta expiry. Artifact retention is independent and may expire without losing structured receipt evidence. No arbitrary 30-day replay cliff. Operator-approved tenant erasure must stop consumers and drain/quarantine pending, retry, and DLQ entries first. Unknown or erased scan IDs never recreate scans; hold/quarantine late deliveries rather than treating receipt absence as successful completion. Retention capacity is part of the R12 storage review, not permission to delete customer records now.

### Close legacy mutation paths

After coordinated cutover, reject unversioned completion. Disable internal `POST /scans/{scan_id}/findings`, `POST /scans/{scan_id}/scanner-runs`, and `PATCH /scanner-runs/{run_id}` as authoritative writes with HTTP 410. Move any required progress use to attempt-fenced advisory fields that cannot create/update final ScannerRun evidence. Fence `PATCH /scans/{scan_id}/status` and prohibit terminal completion, cancellation reversal, summary replacement, and findings mutation there. Fence upload URLs and finalization too. Remove calls to post-completion disappearance helpers outside the completion transaction. API routes and direct services enforce the same checks; route-only RBAC is insufficient.

## Cancellation and queue terminal decisions

Preserve ScanStatus values; add durable `cancellation_state = none | cancel_requested | cleanup_pending | canceled` and cleanup receipt fields. Cancellation is a terminal execution decision at request acceptance, not a successful completion. The cancellation transaction locks Scan, verifies owner/admin/security_reviewer authorization and resource scope, writes actor/time/reason/stable cancellation receipt, sets status `canceled` and state `cancel_requested`, revokes execution authority, and commits. Completion and cancellation linearize at the first successful terminal transaction commit under the same Scan lock. A failed transaction wins nothing. Completion first means cancellation returns 409 `already_completed`. Cancellation first means all later completion returns 409 `scan_canceled`. Repeated cancellation returns the original receipt without changing its actor/reason.

External `Scan.status` is `canceled` only as a cancellation decision projection, while internal cancellation substate records cleanup progress. Readers, UI, and GitHub must render `cancel_requested` and `cleanup_pending` as cancellation in progress, never fully canceled. While either substate is active, no delete, rerun, terminal projection, or queue acknowledgement is allowed. `canceled` substate is required before cancellation acknowledgement or fully-canceled presentation. `cancel_requested` means cleanup has not yet been confirmed. A cleanup failure, unreachable host, or elapsed 30-second cleanup budget sets `cleanup_pending` and alerts. `canceled` means the API has committed a cleanup receipt proving no active container/process/source/output workspace remains for all attempts of the scan, including staged artifact cleanup or a recorded safe garbage-collection obligation. A scan canceled while queued can move directly through request acceptance to `canceled` in the same transaction only when the execution registry proves no attempt/resources were issued. Unknown resource ownership means cleanup pending, not success. For an unreachable host, the API marks cleanup pending and the operator is the fencing authority. A 30-second cleanup timeout starts recovery, not success; the operator must fence or replace the host within the documented recovery SLA, record host/incarnation, fence actor, time, scope, and provider/host receipt in a durable fence receipt, and retain the queue entry or a recoverable quarantine record. A replacement worker may start only after that receipt commits and the API grants a new attempt. Repeated recovery is idempotent and cannot clear pending state without fresh inspection evidence.

The dedicated worker recovery loop owns cleanup retries every 30 seconds; operator host fencing/replacement owns unreachable-host recovery. Cleanup capability is separate from execution mutation authority, so an authorized replacement worker can finalize cleanup without reviving an attempt. Record host/incarnation, attempt/container IDs, inspection outcome, time, and worker/operator actor. On any node with unknown reachability, require host fencing proof instead of claiming a Docker list from a different host proves cleanup. State `cleanup_pending` remains durable across API/worker restarts and has no automatic success timeout.

Queue acknowledgement is authorized by either committed completion receipt or committed cancellation receipt with state `canceled` and confirmed cleanup. A successful completion also requires local execution cleanup before final acknowledgement. Pending cancellation, failed cleanup, API outage, or a local flag is insufficient. Retry and dead-letter transfer may acknowledge the original only after durable recoverable successor/DLQ storage, with idempotent transfer identity. They are transport handoffs, not completed scanning. Exhausted execution failure must have an API failure receipt; no error handler may overwrite a terminal success/cancellation. Queue/API divergence retains recovery state and alerts. This explicitly resolves ADR-009/spec wording that otherwise describes only successful-completion acknowledgement; record it as an exception in an ADR after R03 review, not as an already implemented exception.

## Human transitions and precedence

Owner, admin, and security_reviewer may perform the reviewer/risk-approver actions below, matching the current finding mutation route role set. Developer and viewer cannot mutate finding state, including bulk and direct-service paths. Verify active membership, organization, project, finding, duplicate target, evidence ownership, and actor inside the service before any write. Worker principals may record evidence only; named API system actors own automatic transitions.

| Action | Source | Target | Required data |
| --- | --- | --- | --- |
| Start review | open, to_fix | reviewing | actor, event |
| Assign remediation | open, reviewing | to_fix | actor, event |
| Accept risk | open, reviewing, to_fix, not_observed | accepted_risk | nonempty reason, review_at or expires_at within 90 days |
| Classify false positive | open, reviewing, to_fix, not_observed | false_positive | reason and evidence reference |
| Mark duplicate | open, reviewing, to_fix, not_observed | duplicate | reason and accessible same-project/repository canonical target; reject self-targets and cycles |
| Reopen | accepted_risk, false_positive, duplicate, not_observed, fixed | open | reason |
| Verify remediation | open, reviewing, to_fix, not_observed | fixed | reason and explicit owned evidence reference; fixed_version alone is insufficient |
| API absence | open | not_observed | first qualifying observation and all unresolved branch obligations satisfied |
| API second absence | not_observed | fixed | two qualifying observations and all unresolved branch obligations satisfied |
| API reappearance | not_observed, fixed | open | ordered positive evidence, counter reset |
| API risk expiry/review due | accepted_risk | open | stored due date and named expiry actor |

Reject all unlisted edges with HTTP 409 `invalid_transition`. Same-state requests with identical authorized metadata are no-ops; changed metadata uses a separately audited update, never a transition bypass. Bulk changes validate all members first and commit atomically. Suppression rules remain distinct from finding dispositions. New/renewed suppression rules require reason and review/expiry within 90 days; due rules stop matching pending review.

Human `reviewing` and `to_fix` block automatic absence transitions. Record observations without moving those states. Accepted risk, false positive, and duplicate also remain unchanged on presence/absence. Reappearance reopens machine-closed and manually fixed findings only with evidence ordered after the manual verification checkpoint; older evidence cannot undo a human decision. Manual reopen clears absence counters and records the latest known ref checkpoints, so old/delayed receipts cannot immediately reclose it. Automatic transitions after manual actions require new scans issued after that decision as well as qualifying commit order. All actions lock the finding row and increment an event revision; clients provide expected revision, with stale writes returning 409. Completion takes the same lock. Human disposition committed first takes precedence; a later authorized human action can override a system transition only through a listed edge.

Risk review/expiry uses the earlier supplied date. Check due dates before lifecycle mutation and on reads; show overdue decisions as inactive/open even if the background sweeper is late. The API sweeper commits one idempotent expiry event and resets counters. Reapproval needs a new reason/date. False positive and duplicate have no mandatory automatic expiry in v1; risk and suppression do. Presence does not silently cancel a current risk decision.

### Legacy state migration

Preserve known existing state strings and events, mark old decisions `legacy_unverified`, and reset old `not_observed_count` counters to non-authoritative history. Legacy `not_observed` and `fixed` stay visible with `Evidence unknown`, not verified fixed credit. They require new positive baseline or explicit reviewer verification before automatic policy applies. Do not invent actors, reasons, dates, ancestry, or versions.

If legacy `suppressed` exists, preserve its original label in migration metadata and map to open with `needs_review`, not false positive. For false-positive rows created through the existing suppress alias, mark unknown intent unless an explicit event establishes the classification. Legacy accepted-risk or suppression decisions lacking a reason/date are inactive pending reviewer reapproval and count as open exposure; preserve the original state in history. Unknown strings map to open/needs_review with the original value retained. Duplicate without valid target remains legacy-unverified, is not followed as a canonical redirect, and requires review. Historic false-positive/duplicate/fixed dispositions do not become compliant merely by renaming them. Migrate once with an idempotent named migration actor and retain row/event counts for reconciliation. No silent bulk acceptance.

## Bounded payload policy

These are concrete candidate v1 limits, not measured capacity claims. Gate G1 in the decision table remains open because the baseline has no approved representative beta payload/capacity receipt. Do not enable v1 until the operator approves the measured envelope or records amended numbers here.

| Resource | Candidate hard limit |
| --- | --- |
| Completion body | 16 MiB uncompressed UTF-8 JSON; reject compressed request bodies in v1 |
| Finding candidates | 10,000 per scan, including duplicates before validation |
| Scanner outcomes | 7, also exactly the persisted expected set |
| Artifact descriptors | 32 per scan; artifacts uploaded separately, never embedded in completion |
| Artifact bytes | 64 MiB each, 256 MiB total per scan; raw secret artifacts remain prohibited |
| Metadata | 16 KiB serialized JSON per finding/instance/run; 1 MiB total arbitrary metadata; depth 8, 128 keys per object |
| References | 32 per finding; 50,000 per scan |
| Strings | 8,192 UTF-8 bytes general text, 2,048 path/URL bytes, 512 title bytes, 64 version bytes, 50 scanner-name bytes; lowercase SHA-256 digest exactly 64 hex characters |
| Scope lists | 10,000 changed paths, 256 normalized include/exclude patterns |

Byte limits apply before parse using a streamed cap, even without Content-Length; structure limits apply before any durable writes. HTTP 413 `payload_limit_exceeded` identifies the violated limit without echoing sensitive contents. Schema/provenance failures use 422. Reject the entire completion, never truncate findings into apparent absence. Persist no terminal success on rejection; retain the attempt's recoverable failure reason outside evidence completion under fencing. Oversized scanner output is `failed` with a size reason, not successful empty. No chunking in v1. At the maximum allowed payload, R04 must prove bounded memory, transaction duration, rollback, and p95 under concurrent beta traffic. Host capacity and sanitized fixture size distribution decide G1, not a guessed multiplier.

## Acceptance and ADR disposition

All ten decision rows plus G1 must receive review. No runtime work is complete merely because this policy exists. Required later evidence uses concurrent PostgreSQL sessions, real Redis Streams and the supported REST interface, actual Docker daemon/host inspection, authenticated browser flows, and pinned-image scanner fixtures. Mock-only or skipped tests do not satisfy those gates.

Keep this policy as the amended review contract until G1 and independent review close. Then record one new ADR for attempt fencing, replay, and cancellation exceptions using the next available number. Do not mark the proposed September spec or this policy Accepted by inference, and do not alter accepted ADRs in this documentation-only slice.

## References

- [Readiness spec](2026-09-13-evidence-first-readiness.md)
- [Readiness plan](../docs/plans/2026-09-13-evidence-first-readiness-plan.md)
- [Approved beta specification](SECURE_PRIVATE_BETA.md)
- [Canonical findings ADR](../docs/adr/ADR-002-canonical-finding-model.md)
- [Lifecycle ownership ADR](../docs/adr/ADR-003-scan-lifecycle-architecture-program.md)
- [Finding policy ADR](../docs/adr/ADR-004-finding-lifecycle-policy.md)
- [Worker isolation ADR](../docs/adr/ADR-009-dedicated-workers-for-private-beta.md)
- [Role definitions](RBAC.md)
