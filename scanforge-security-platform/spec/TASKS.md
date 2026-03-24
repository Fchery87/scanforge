# Implementation Tasks

## Foundation
- [ ] initialize monorepo
- [ ] configure Python packaging for API and worker
- [ ] configure Next.js app
- [ ] create Neon database
- [ ] configure Alembic
- [ ] configure Upstash Redis
- [ ] configure R2 bucket
- [ ] configure Render services
- [ ] configure Vercel project

## API
- [ ] create health endpoints
- [ ] create auth integration layer
- [ ] create organization/project/repository CRUD
- [ ] create scan trigger endpoint
- [ ] create findings list/detail endpoints
- [ ] create audit log writes

## Worker
- [ ] implement queue consumer
- [ ] implement repository fetcher
- [ ] implement scanner adapter interface
- [ ] implement Trivy adapter
- [ ] implement Gitleaks adapter
- [ ] implement OSV adapter
- [ ] implement normalization pipeline

## Frontend
- [ ] auth shell
- [ ] dashboard
- [ ] repositories page
- [ ] scans page
- [ ] findings page
- [ ] finding detail drawer/page
- [ ] reports page
