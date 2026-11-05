# Render Blueprint

[render.yaml](../../render.yaml) is authoritative. It currently defines:

1. `scanforge-api`: the FastAPI web service.
2. `scanforge-maintenance`: a weekly cron for maintenance and stale-lease recovery.
3. `scanforge-scan-dispatch`: a per-minute cron that delivers durable scan dispatch obligations.

No scanner worker or scheduler runs on Render. Scanner execution runs on dedicated per-organization hosts (ADR-011); recurring scheduling is deferred. Environment groups and the credentials each must never contain are documented as comments in `render.yaml`.
