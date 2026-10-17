# ADR-017: Authoritative scan evidence and optional AI

## Status

Accepted on 2026-10-16, Round 8 Q42–Q45. AI remains disabled for the initial beta.

## Completion authority

The API derives completeness, counts, lifecycle eligibility and artifact ownership from validated evidence and the immutable execution contract. Worker summaries cannot grant authority. Validate and sanitize before computing a versioned canonical digest. Specify canonical JSON and deterministic ordering of unordered collections; reject duplicate JSON keys, unknown contract fields, duplicate scanner identities and invalid numbers.

Commit findings, scanner outcomes, finalized artifact references, derived summaries, audit and receipt atomically. Identical authorized replay returns the original business result; changed evidence conflicts and superseded attempts cannot write. An enabled replacement principal with explicit read authority may recover receipts without gaining historical write authority.

## AI capability and data authority

Introduce finding explanation before independent AI code review, as separately named and evaluated capabilities. Explanation consumes validated findings, grants no detection credit and cannot change disposition. Code review proposes new findings from verified changes/context within declared supported classes.

Require organization opt-in, identified provider/model and disclosed data scope. Source-context processing requires additional explicit consent beyond metadata explanation. No silent provider or data-scope fallback. Initially exclude secret findings from external AI. Revocation prevents new requests and cancels pending work where possible, without claiming recall of already-sent data.

All repository/provider content is untrusted evidence. AI receives bounded, authorized context and no service/runtime credentials. Initial AI has no command execution, unrestricted network or mutation tools. Retrieval enforces tenant/repository/revision/file boundaries. Validate generated schemas and code locations; withhold unsupported claims or label uncertainty. Human approval precedes disposition changes, patches or external issue creation. Patch execution needs a later sandbox design.

## Separate processing

Complete scanning and cleanup independently. Explanations run as separate durable jobs against accepted evidence. Bound concurrency, context, tokens, elapsed time, retries and organization spending. Exhaustion is explicit skipped/deferred work. AI failure cannot change scan outcome or evidence digest.

Round 9 Q48, accepted on 2026-10-16: metadata explanation uses accepted structured evidence. Source-based review acquires context in a separately authorized, bounded ephemeral job that rechecks current access and retrieves the exact revision. Independently clean that workspace. If access or revision is unavailable, skip explicitly; never retain the original scan workspace or substitute current source.

Cache within the organization using evidence/content identity, relevant revision, model, prompt, retrieval policy and output-schema version. Consent changes and erasure invalidate affected entries. Measure usage/cost/latency/cache/failures separately from scanner completeness. Provider/model changes require evaluation before rollout.

## Rationale

Server-derived immutable evidence makes accepted results independent of worker summaries and optional AI. Separate authority, consent and processing prevents annotation failures or hostile repository instructions from controlling trusted state.
