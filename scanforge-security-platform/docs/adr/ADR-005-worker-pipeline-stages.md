# ADR-005: 3-stage scan orchestrator decomposition

## Status
Accepted

## Decision
Decompose the monolithic `ScanOrchestrator.process_job` into three discrete stages:
`ScanExecutionStage`, `NormalizationStage`, and `PersistenceStage`, each in its own module under `apps/worker/app/services/scan_pipeline/`.

## Rationale
The original orchestrator exceeded 500 lines with mixed concerns: git cloning, scanner execution, artifact upload, finding normalization, and notification dispatch all lived in a single class and single method. This made:

- Unit testing hard (all side effects interleaved)
- The AI investigation stage slot unclear (the insertion point for the planned AI stage is between normalization and persistence)
- Logging inconsistent (print() mixed with ad-hoc exception handling)

The 3-stage decomposition:
- Provides a named slot (`AIInvestigationStage`) between `NormalizationStage` and `PersistenceStage` for the upcoming AI annotation pass
- Makes each stage independently testable against the shared `ScanContext`
- Centralizes structured JSON logging and Slack alert dispatch in the orchestrator

## Consequences
The `ScanOrchestrator` retains thin wrappers (`_get_scanners_for_type`, `_build_completion_summary`) for backward-compat with existing tests. All internal state passes through `ScanContext`. Adding the AI stage requires inserting one call between the normalization and persistence steps in `process_job`.
