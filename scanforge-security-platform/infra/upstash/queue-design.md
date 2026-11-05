# Queue Design

Redis Streams are a delivery mechanism, not the source of truth for scans, dispatch obligations or findings; PostgreSQL is.

Each organization has its own stream, `queue:scans:{organization_id}`, with a dead-letter stream `queue:scans:{organization_id}:dlq` (see the [dead-letter runbook](../../docs/runbooks/dead-letter-recovery.md)). Producers and the payload contract are in the API [queue client](../../apps/api/app/clients/queue.py) and [queue contract](../../apps/api/app/contracts/queue.py); the worker side is in [apps/worker/app/clients/queue.py](../../apps/worker/app/clients/queue.py). Job types map to scan types in the [dispatch service](../../apps/api/app/services/scan_dispatch.py).
