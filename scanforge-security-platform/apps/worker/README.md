# Worker

Python worker for scan execution, scheduling, and maintenance tasks.

## Responsibilities

- dequeue scan jobs
- request authenticated clone information from the internal API
- clone repositories into temporary working directories
- run configured scanner adapters
- upload raw output and generated artifacts to S3-compatible storage
- normalize scanner output into the canonical finding shape
- persist findings and scanner-run status through internal API routes
- dispatch scan notifications

## Entry Points

- `app.worker.main`: main queue consumer
- `app.worker.scheduler`: scheduled scan dispatch
- `app.worker.maintenance`: queue cleanup and operational utilities

## Run Locally

```bash
PYTHONPATH="$(pwd)/apps/worker" apps/worker/.venv/bin/python -m app.worker.main
```
