# ADR-013: Durable scan delivery, recovery, and terminal evidence

## Status

Accepted on 2026-10-16, Round 4 Q18–Q23. This refines ADR-003 and ADR-009. Timing and capacity values remain provisional pending measurements.

## Delivery and retries

Create the scan, accepted trigger identity, and enqueue obligation in one database transaction. A dispatcher retries queue delivery. Equivalent automatic triggers and repeated manual idempotency keys return the original scan/business response; explicit manual reruns create new scans. Awaiting dispatch is visible independently of execution. Queue outages retain accepted obligations and alert operators.

Round 9 Q52, accepted on 2026-10-16: automatic push scanning promises latest-state coverage. A newer descendant may explicitly supersede unstarted automatic work within the same branch generation. Preserve accepted trigger/scan records, superseded outcomes and skipped coverage; never fabricate observations. Running work is not implicitly superseded, and coalescing cannot cross force-push boundaries. Manual requests are never silently coalesced; reject excess manual work before acceptance with actionable capacity status. Every accepted obligation remains accounted for, including supersession.

Transient provider, API, storage, and queue failures receive bounded retries with backoff and jitter. Invalid authority, inaccessible revision, unsupported contract, and exceeded limits stop with actionable reasons. Individual scanner failures preserve partial findings and allow a new scan. A lost completion response retrieves or replays accepted evidence without rescanning. Notification retries are independent. Exhausted execution retries retain a durable failure and recoverable dead-letter record. Three total execution attempts are the starting candidate; retry timings and guarantees require measurement. Operator recovery is audited, and completed scans cannot acquire replacement results.

## Execution authority and cleanup

Bind execution to worker principal, process incarnation, attempt, revision, and live database lease. Fence progress, upload/finalization, scanner outcomes, findings, and completion. Queue reclaim grants no authority. Lost authority stops execution. A successor starts only after old execution is confirmed stopped or its host fenced; unknown host state blocks recovery visibly and alerts the operator. The current 120-second lease and 30-second renewal remain measurement candidates.

Cancellation and completion serialize under the same scan lock; the first committed terminal decision wins. Canceled scans expose cleanup pending until subprocesses, containers, source and temporary outputs are confirmed removed. Cleanup obligations survive restarts. Queue acknowledgement follows a durable terminal receipt and required cleanup for cancellation and successful completion. An unreachable host is a cleanup incident, not proof of deletion. This is the explicit cancellation acknowledgement exception to ADR-009's completion-only acknowledgement wording.

## Durable evidence

Retain source only during execution and cleanup. Retain sanitized scanner artifacts for 90 days. Retain structured findings, observations, triage, provenance, and completion receipts for the organization's lifetime, subject to explicit tenant erasure. Raw secret reports never persist. Apply the secret boundary to other scanners' output as well.

Finalized artifacts are immutable and bind organization, scan, attempt, scanner, checksum and size. Validate object ownership and current user authority at download; display expiration. Separate staging objects from finalized evidence and clean staging on a short-lived policy. ADR-015 defines backup retention and erasure; enforcement evidence and the staging cleanup interval remain outstanding.

Round 9 Q54, accepted on 2026-10-16: upload and verify immutable objects before publishing validated references atomically with the database receipt. There is no shared object-store/database transaction. Unreferenced objects remain inaccessible and are garbage-collected. Preserve valid structured findings when secondary artifacts are unavailable; artifact availability is separate from scanner coverage. Evidence essential to validating an observation must be available before that observation is verified. Check existence, ownership, size and checksum before publishing download references. ADR-015 defines backup retention; the staging cleanup interval remains an operating parameter to specify and verify.

## Audit

Persist audit events in the same transaction as security-sensitive mutations; an audit write failure rolls back the mutation. Cover installation bindings, membership/roles, repository changes, finding decisions, cancellation, worker credential administration, and operator recovery. Record actor, verified organization, target, action, reason, revision, and appropriate before/after values without sensitive fields. Denied requests are separate security telemetry; downloads create access events. Application roles cannot edit audit history; tenant erasure is an explicit exception.

## Rationale

Database-owned delivery obligations survive queue outages. Fenced attempts and durable cleanup prevent redelivery from creating concurrent authority or false deletion claims. Immutable evidence and transactional auditing preserve the meaning of an accepted result independently of response loss and notification delivery.
