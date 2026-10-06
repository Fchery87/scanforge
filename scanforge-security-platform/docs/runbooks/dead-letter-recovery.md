# Dead-letter recovery

1. Inspect the organization's `queue:scans:{organization_id}:dlq` stream without copying payloads into logs.
2. Confirm the source repository, scan state, and failure reason in PostgreSQL.
3. Correct the worker or scanner defect before replaying.
4. Re-enqueue only the scan ID through `ScanLifecycleService`; do not manually edit Redis keys.
5. Keep the DLQ record until the replay completes successfully.
6. Verify atomic completion and one finding instance per occurrence.
