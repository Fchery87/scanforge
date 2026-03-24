# Worker

Python background worker intended for Render Background Worker deployment.

## Responsibilities
- claim scan jobs
- fetch repository snapshot
- run scanner adapters
- upload raw artifacts to R2
- normalize findings
- call API/internal services to persist results
