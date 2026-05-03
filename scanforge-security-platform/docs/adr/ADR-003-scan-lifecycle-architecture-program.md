# ADR-003: Scan lifecycle architecture program

## Status

Accepted

## Context

ScanForge's core product value depends on a reliable scan lifecycle: scans are created, queued, executed by workers, associated with scanner runs, connected to raw artifacts, normalized into canonical finding candidates, persisted as findings, and surfaced in scan history and finding review.

The current architecture spreads scan lifecycle decisions across route handlers, scheduling code, queue clients, worker orchestration, scanner adapters, normalizers, finding persistence, artifact storage, access checks, and repository onboarding. That makes important invariants easy to duplicate or omit.

The highest-risk invariant is that a scan record and its queue job must agree on execution context. Manual scans and scheduled scans should not construct separate queue payload shapes or independently decide scan type mapping, retry meaning, or failure behavior.

ADR-002 remains in force: all scanner output must normalize into one internal finding model, and raw tool outputs are never the primary UI contract.

## Decision

Treat scan lifecycle as the central architecture program for ScanForge.

The scan lifecycle Module owns the product meaning of scan creation, queueing, worker execution, completion, failure, retry, and dead-letter handling. Scan creation and enqueue should be treated as one scan lifecycle outcome at the Interface. Callers should not compose scan persistence and queue enqueue by hand.

Manual scans, scheduled scans, and future scan triggers should use the same scan lifecycle Interface. Scheduling may continue to run in a separate process, but it should act as a trigger Adapter rather than owning scan creation or queue payload construction.

Queue payloads should carry only scan execution identity and immutable execution hints. The worker should load authoritative scan lifecycle context from the system of record before cloning, updating statuses, running scanners, or sending notifications.

The queue Module owns queue mechanics such as enqueue, dequeue, requeue, status storage, retry counters, and DLQ movement. The scan lifecycle Module owns retry and DLQ meaning: when a scan should retry, when it has failed, and what product state follows.

## Adjacent Modules

Scanner output normalization is a separate deepened Module behind scan lifecycle. Scanner Adapter Modules should own scanner-specific execution metadata and scanner-specific normalization capability. They should not own durable finding persistence.

Canonical finding persistence is a separate deepened Module behind scan lifecycle. It owns how canonical finding candidates become findings, finding instances, finding events, and finding references.

Raw artifacts visibility is split between internal scanner run storage references and user-visible scan history download behavior. Raw artifacts support auditability and debugging; they are not the primary UI contract for findings.

Access is adjacent to scan lifecycle. Organization, project, repository, and role checks should live in an access Module rather than being owned by scan lifecycle, because findings, repositories, scans, projects, and exports all need access decisions.

Repository onboarding is adjacent to scan lifecycle. It observes scan lifecycle progress but should not own scan lifecycle behavior or queueing rules.

## Consequences

Future changes to scan creation, scheduling, queue payloads, retry, or DLQ behavior should start at the scan lifecycle Interface.

Future changes to scanner-specific raw output handling should start at scanner output normalization, not at scan lifecycle.

Future changes to finding deduplication, fixed-finding reopening, finding instance evidence, or finding references should start at canonical finding persistence, not at scanner adapters.

Future changes to artifact downloads should preserve the split between internal raw artifact references and scan history download behavior.

Future changes to authorization should deepen access directly rather than adding more checks to scan lifecycle.

Future changes to onboarding should derive progression from domain facts rather than duplicating scan lifecycle rules.

## Implementation Guidance

The first implementation slice should deepen the scan lifecycle Interface around scan creation and enqueue.

That slice should make manual scans and scheduled scans share the same scan/job invariants, reduce queue payload shape drift, and keep enqueue failure handling inside the scan lifecycle Module.

Raw artifacts visibility, access, repository onboarding, scanner output normalization, and canonical finding persistence should be handled in later slices after the scan lifecycle Interface is stable.
