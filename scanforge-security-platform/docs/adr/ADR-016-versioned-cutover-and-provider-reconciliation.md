# ADR-016: Versioned cutover and provider reconciliation

## Status

Accepted on 2026-10-16, Round 7 Q36–Q37.

## Decision

Version worker/API contracts and publish an explicit compatibility matrix. Drain or cancel legacy attempts before cutover, reject unsupported producers, and disable authoritative legacy writes. Use staged migrations, repeatable legacy reconciliation and a tested rollback. Pilot a test organization and one design partner before cohort expansion. Rollback preserves receipts and deletion tombstones and cannot silently reinterpret new evidence or resurrect erased data. Release identity includes source revision, schema version, worker version and scanner-image digest.

Periodically reconcile GitHub installation access, immutable repository identity, default branch and current head. Reverify authority before cloning. Enqueue an authorized current head without a scan through normal durable dispatch. Record observation gaps when intervening continuity is unknown; never invent scans or absence receipts. Default-branch changes are explicit scope changes that retain old obligations. Reconciliation cadence requires operating measurements.

## Rationale

Versioned cutover prevents older producers from bypassing new authority and evidence semantics. Reconciliation detects missed provider events without treating incomplete webhook history as evidence of remediation.
