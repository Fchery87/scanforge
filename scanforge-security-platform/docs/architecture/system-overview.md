# System Overview

## Runtime topology

- Vercel hosts the Next.js application
- Render hosts:
  - FastAPI API service
  - Python background worker
  - cron jobs for scheduled scans and maintenance
- Neon Postgres stores normalized application data
- Cloudflare R2 stores raw scan artifacts and exports
- Upstash Redis stores queue state, locks, and short-lived cache

## Core flow

1. User connects a repository
2. API creates a scan record
3. Worker pulls a job from the queue
4. Worker fetches repo snapshot and runs scanner adapters
5. Raw artifacts upload to R2
6. Findings normalize into the canonical schema
7. Dashboard updates from normalized findings and scan summaries
