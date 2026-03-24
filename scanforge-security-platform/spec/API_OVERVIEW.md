# API Overview

Base path: `/api/v1`

## Health
- `GET /health`
- `GET /ready`

## Organizations and projects
- `POST /organizations`
- `GET /organizations`
- `POST /projects`
- `GET /projects/:project_id`

## Repositories
- `POST /projects/:project_id/repositories`
- `GET /projects/:project_id/repositories`

## Scans
- `POST /projects/:project_id/scans`
- `GET /scans/:scan_id`
- `GET /projects/:project_id/scans`

## Findings
- `GET /projects/:project_id/findings`
- `GET /findings/:finding_id`
- `POST /findings/:finding_id/suppress`

## Reports
- `POST /projects/:project_id/exports`
- `GET /exports/:export_id`

## Audit
- `GET /organizations/:organization_id/audit-logs`
