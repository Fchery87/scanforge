# ADR-012: Repository authority and ordered finding evidence

## Status

Accepted on 2026-10-16, Round 3 Q12–Q17. This refines ADR-002 and ADR-004. It accepts the semantics below, not unmeasured operational defaults from the September decision table.

## Repository authority and scope

For beta, each GitHub installation binds to one ScanForge organization, and each connected repository belongs to one project in that organization. Verify authority before reserving a binding. Identity uses immutable provider IDs. Rebinding is an explicit audited administrative operation and never implicitly transfers history, credentials, or authorization. Repository sharing across projects is deferred.

Automatic push scanning covers the verified default branch. Authorized users may manually request another named branch. Findings and coverage show branch scope, and observations remain separate by branch generation. Automatically scanning additional branches requires a later capacity decision.

## Immutable scan identity

Resolve the exact commit before enqueueing and retain immutable repository ID, full branch ref, generation, expected scanners, and coverage policy. Workers fetch and verify that revision; inaccessible revisions fail explicitly. Running again resolves the current revision, while historical reproduction explicitly requests the original revision.

Renames preserve history for the same immutable repository ID. Transfers and installation-access changes require authorization revalidation. Force pushes, branch recreation, and unknown ancestry establish a new generation and reset comparability. Removal of repository access stops new scans, revokes execution access, and triggers active-work cleanup. These events never prove remediation; unresolved historical exposure requires explicit reconciliation.

## Finding observations and human decisions

Automatic closure requires two full, healthy, comparable absence observations on distinct descendant commits for every branch generation where the finding was observed. The first qualifying absence permits not_observed; the second permits fixed. Same-commit reruns do not count. Partial coverage, unknown ancestry, incompatible provenance, and unresolved branch obligations block closure. Exact scanner provenance is required initially; directional compatibility across upgrades requires approved fixtures. Apply observations by verified commit order. Delayed presence between absence observations invalidates the closure they purportedly establish.

Reviewing and to_fix remain unresolved and block automatic absence transitions. Accepted risk, false positive, and duplicate dispositions survive observations, which remain recorded. Verified presence after manual fixed reopens a finding, while older evidence cannot override a newer decision. Manual reopening clears absence evidence and requires new scans before automatic closure.

Risk acceptance requires a reason and expiry; expiry returns the finding to unresolved exposure. Duplicate targets must belong to the same repository and cannot form cycles. Mutations require an expected revision, stale writes conflict, and bulk actions are all-or-nothing. Owners, admins, and security reviewers retain finding mutation authority; developers and viewers are read-only for those decisions.

## Round 9 refinements

Accepted on 2026-10-16, Q49, Q51 and Q53. Manual fixes identify resolved branch obligations and include reason/evidence. Other unresolved obligations retain repository exposure; a global fix explicitly accounts for every active obligation. Repository-wide accepted-risk and false-positive judgments expose affected branches/scope and never rewrite observations or establish remediation.

Human duplicate groups aggregate presence and branch obligations across members and count once. Any unresolved member keeps group exposure unresolved. Canonical target changes are audited and cycle-free, preserve history, and require explicit review of affected human dispositions. Target deletion, retirement or reclassification cannot discard group evidence. Grouping is distinct from automatic fingerprint equivalence.

Low-activity repositories may require evidence-backed human resolution when two distinct comparable commits cannot occur within freshness constraints. Explain blocked closure and missing evidence. Never weaken freshness, count same-commit reruns twice or manufacture commits to obtain closure.

## Rationale and remaining work

These rules prevent mutable names, arrival order, repeated scans, and changes to scanner coverage from masquerading as remediation. Two absences are a conservative policy, not proof of vulnerability absence.

Implementation requires persisted provenance, ordered observations, service-level authorization, concurrency control, conservative migration, and PostgreSQL concurrency tests. ADR-014 defines freshness and legacy evidence; ADR-015 defines retired-branch reconciliation. Transition matrices and measured operating envelopes must implement the accepted semantics and retain reviewable evidence.
