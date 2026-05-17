# Scan Lifecycle Architecture Program

## Purpose

This plan turns the scan lifecycle architecture review into executable vertical slices. It gives a future engineer or agent a clear order for deepening the scan lifecycle Module while preserving the adjacent Modules defined in ADR-003.

When this program is complete, manual scans, scheduled scans, queue jobs, worker execution, scanner output normalization, canonical finding persistence, raw artifacts visibility, access, and repository onboarding will line up around stable seams instead of duplicating scan lifecycle knowledge.

## Context

The source architecture decision is ADR-003: scan lifecycle is the central architecture program for ScanForge.

The domain terms are defined in the project context file:

- scan lifecycle
- scanner output normalization
- canonical finding persistence
- raw artifacts visibility
- access
- repository onboarding

The accepted direction is:

- Scan creation and enqueue are one scan lifecycle outcome at the Interface.
- Manual scans, scheduled scans, and future scan triggers use the same scan lifecycle Interface.
- Queue payloads carry scan execution identity and immutable execution hints, not duplicated authoritative context.
- The queue Module owns queue mechanics.
- The scan lifecycle Module owns retry and DLQ meaning.
- Scanner output normalization, canonical finding persistence, raw artifacts visibility, access, and repository onboarding remain adjacent Modules.

## Architecture Direction

Deepen the scan lifecycle Module first. It should hide scan persistence, queue job creation, queue payload shape, enqueue failure behavior, worker execution context, retry policy, and DLQ meaning behind a smaller Interface.

Keep adjacent Modules separate:

- Scanner output normalization owns scanner-specific raw output shape and canonical finding candidate construction.
- Canonical finding persistence owns deduplication, fixed-finding reopening, finding instance evidence, and finding references.
- Raw artifacts visibility separates internal scanner run storage references from user-visible scan history download behavior.
- Access owns organization, project, repository, and role checks.
- Repository onboarding observes domain facts and does not own scan lifecycle behavior.

## Slices

- [ ] **S01: Deepen Manual Scan Creation And Enqueue** `risk:high` `depends:[]` `mode:AFK`
  > After this: a manual scan request creates one scan lifecycle outcome that either creates and enqueues the scan or records enqueue failure inside the scan lifecycle Module.

  Move scan record creation, scan type mapping, queue job construction, and enqueue failure handling out of route choreography and behind a scan lifecycle Interface. Preserve existing access behavior at the route edge.

- [ ] **S02: Route Scheduled Scans Through The Same Interface** `risk:high` `depends:[S01]` `mode:AFK`
  > After this: a due schedule triggers the same scan/job invariants as a manual scan, and scheduler-specific payload drift is gone.

  Treat the scheduler as a trigger Adapter. It should identify due schedules and call the scan lifecycle Interface rather than hand-building scan records and queue payloads.

- [ ] **S03: Centralize Queue Contract Mechanics** `risk:high` `depends:[S01]` `mode:AFK`
  > After this: API and worker code share one queue job contract for scan lifecycle jobs, including retry and DLQ mechanics.

  Reduce API/worker queue duplication or add shared contract tests if physical sharing is not yet practical. Queue mechanics stay in the queue Module; scan lifecycle meaning stays outside it.

- [ ] **S04: Load Worker Scan Context Authoritatively** `risk:high` `depends:[S01,S03]` `mode:AFK`
  > After this: the worker can execute a scan from a minimal queue job by loading authoritative scan lifecycle context from the system of record.

  Stop requiring duplicated organization, project, repository, branch, commit, and user context in every queue payload. Add explicit failure behavior for missing or stale scan execution context.

- [ ] **S05: Deepen Scanner Output Normalization Registration** `risk:medium` `depends:[S04]` `mode:AFK`
  > After this: scanner Adapter selection and scanner output normalization are registered together instead of maintained as parallel scan orchestration maps.

  Give each scanner Adapter Module ownership of its scanner-specific execution metadata and normalization capability. Keep durable finding persistence separate.

- [ ] **S06: Tighten Canonical Finding Persistence Interface** `risk:medium` `depends:[S05]` `mode:AFK`
  > After this: canonical finding candidates persist through a stricter Interface that owns deduplication, reopening, instances, events, and references.

  Replace loose dict assumptions at the persistence seam with an explicit canonical finding candidate contract. Preserve ADR-002: raw scanner output is never the primary UI contract.

- [ ] **S07: Preserve Raw Artifacts Visibility Boundary** `risk:medium` `depends:[S04,S05]` `mode:AFK`
  > After this: raw artifact storage references remain internal while scan history exposes access-checked download behavior.

  Keep scanner run storage references separate from user-visible scan history download URLs. Preserve redaction of storage keys in scan detail responses.

- [ ] **S08: Deepen Access As An Adjacent Module** `risk:medium` `depends:[S01]` `mode:AFK`
  > After this: scan, finding, artifact, repository, and schedule mutations use shared access leverage points instead of repeated route-local checks.

  Centralize organization, project, repository, and role checks where practical. Do not put access ownership inside the scan lifecycle Module.

- [ ] **S09: Remove Repository Onboarding Duplication** `risk:low` `depends:[S01,S06,S08]` `mode:AFK`
  > After this: repository onboarding derives checklist state from canonical organization, project, repository, scan, finding, and schedule facts through one Implementation.

  Remove duplicated onboarding logic and keep repository onboarding as an observer of domain progress, not an owner of scan lifecycle behavior.

- [ ] **S10: Prove End-To-End Scan Lifecycle Integration** `risk:high` `depends:[S02,S03,S04,S05,S06,S07,S08,S09]` `mode:HITL`
  > After this: the assembled scan lifecycle can be demonstrated from repository onboarding through scan execution, finding persistence, raw artifact download, and access-checked retrieval.

  Exercise the integrated path across API, queue, worker, scanner Adapter, scanner output normalization, canonical finding persistence, raw artifacts visibility, access, and repository onboarding. This slice should include a human review of the final seams before the program is considered complete.

## Boundary Map

S01 produces the first scan lifecycle Interface for manual scan creation and enqueue. S02 consumes that Interface from the scheduler trigger Adapter.

S03 produces the queue job contract and queue mechanics. S04 consumes that contract and shifts worker execution context loading away from denormalized payloads.

S04 produces authoritative scan execution context loading for the worker. S05 consumes it when registering scanner Adapter and scanner output normalization behavior behind scan lifecycle.

S05 produces canonical finding candidates from scanner output normalization. S06 consumes those candidates through canonical finding persistence.

S04 and S05 produce scanner run and artifact-producing execution. S07 consumes that execution output while preserving the split between internal raw artifact references and scan history download behavior.

S01 produces scan lifecycle call sites that need access decisions. S08 consumes those call sites and moves repeated access knowledge into access leverage points.

S01, S06, and S08 produce stable domain facts for scans, findings, and access. S09 consumes those facts to simplify repository onboarding.

S10 consumes every prior seam and verifies the assembled scan lifecycle.

## Success Criteria

- Manual and scheduled scans use the same scan lifecycle Interface.
- Queue job payload shape is no longer hand-built differently by manual and scheduled paths.
- Worker execution loads authoritative scan context instead of trusting duplicated payload context.
- Retry and DLQ product meaning belongs to scan lifecycle, not raw queue mechanics.
- Scanner output normalization is registered with scanner Adapters rather than parallel orchestration maps.
- Canonical finding persistence has an explicit input contract and preserves ADR-002.
- Raw artifact storage references remain internal and scan history exposes stable download behavior.
- Access checks are reusable across scan, finding, artifact, repository, and schedule flows.
- Repository onboarding has one Implementation and observes domain facts.
- The final integrated path is demonstrable and covered by tests or contract checks.

## Key Risks

- Scheduled scans currently duplicate scan creation and queue payload construction, which can break worker execution when required context is missing.
- API and worker queue Modules currently diverge, especially around delayed job behavior.
- Shrinking queue payloads requires a reliable internal path for the worker to load scan execution context.
- Scanner output normalization and canonical finding persistence must stay separated so scanner Adapters do not take on durable storage responsibilities.
- Access is adjacent but cross-cutting; centralizing it must not weaken existing authorization behavior.

## Proof Strategy

- Add contract tests for manual scan creation and enqueue outcomes.
- Add scheduled scan tests that prove the scheduler uses the same scan lifecycle Interface.
- Add queue contract tests shared by API and worker or duplicated against the same fixtures.
- Add worker tests for loading scan execution context from the system of record and failing explicitly when context is missing.
- Add scanner output normalization tests per scanner Adapter Module.
- Add canonical finding persistence tests for deduplication, fixed-finding reopening, finding instances, finding events, and finding references.
- Preserve artifact download contract tests that prove storage keys are not exposed as the UI contract.
- Add access tests for each consolidated access leverage point.
- Add an integration test or documented manual verification path for the full scan lifecycle.

## Out of Scope

- MCP access layer work.
- New scanner support beyond what is needed to deepen scanner output normalization registration.
- A new policy engine.
- Full UI redesign.
- Replacing the queue provider.
- Moving all scheduling infrastructure into a new runtime.
- Changing the canonical finding model accepted in ADR-002.
