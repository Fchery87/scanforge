# API Overview

Base path: `/api/v1`

## Health

- `GET /health`
- `GET /ready`

## Organizations

- `GET /organizations`
- `GET /organizations/slug-preview`
- `POST /organizations`
- `GET /organizations/{org_id}`
- `PATCH /organizations/{org_id}`
- `DELETE /organizations/{org_id}`

## Memberships And Users

- membership routes are mounted under `/organizations/{org_id}`
- user self-service routes are mounted under `/users`

## Projects

- `GET /organizations/{org_id}/projects`
- `POST /organizations/{org_id}/projects`
- `GET /organizations/{org_id}/projects/{project_id}`
- `PATCH /organizations/{org_id}/projects/{project_id}`
- `DELETE /organizations/{org_id}/projects/{project_id}`

## Repositories

- `GET /organizations/{org_id}/projects/{project_id}/repositories`
- `POST /organizations/{org_id}/projects/{project_id}/repositories`
- `GET /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}`
- `PATCH /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}`
- `DELETE /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}`

## Scan Schedules

- `GET /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/schedules`
- `POST /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/schedules`
- `PATCH /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/schedules/{schedule_id}`
- `DELETE /organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/schedules/{schedule_id}`

## Scans

- `GET /organizations/{org_id}/projects/{project_id}/scans`
- `POST /organizations/{org_id}/projects/{project_id}/scans`
- `GET /organizations/{org_id}/projects/{project_id}/scans/{scan_id}`
- `GET /organizations/{org_id}/projects/{project_id}/scans/{scan_id}/scanner-runs/{run_id}/download`
- `POST /organizations/{org_id}/projects/{project_id}/scans/{scan_id}/cancel`
- `DELETE /organizations/{org_id}/projects/{project_id}/scans/{scan_id}`

## Findings

- `GET /organizations/{org_id}/projects/{project_id}/findings`
- `GET /organizations/{org_id}/projects/{project_id}/findings/stats`
- `GET /organizations/{org_id}/projects/{project_id}/findings/{finding_id}`
- `GET /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/events`
- `PATCH /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/triage`
- `POST /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/suppress`
- `POST /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/resolve`
- `POST /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/reopen`
- `POST /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/accept-risk`
- `POST /organizations/{org_id}/projects/{project_id}/findings/{finding_id}/mark-duplicate`
- `POST /organizations/{org_id}/projects/{project_id}/findings/bulk`

## Exports, Notifications, Scorecards, Audit

- exports are mounted under `/organizations/{org_id}/projects/{project_id}/exports`
- notifications are mounted under `/notifications`
- scorecard endpoints are mounted under `/organizations/{org_id}/projects/{project_id}/scorecard`
- audit log routes are mounted under organization and project-scoped paths

## GitHub And Webhooks

- GitHub install, OAuth, integration, and repository listing routes are mounted under `/organizations/{org_id}/github/*` and `/github/*`
- webhook routes are mounted under `/webhooks`

## Internal Worker API

Internal routes live under `/internal` and are protected by service auth. They are used for:

- clone URL retrieval
- scan status updates
- scanner run creation and updates
- finding persistence
- worker-generated notifications
