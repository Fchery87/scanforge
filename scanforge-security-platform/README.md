# ScanForge

ScanForge is a pre-beta repository security scanning and triage platform. The implementation contains a Next.js application, FastAPI API, PostgreSQL models and migrations, and a Python scanning worker. It is not yet a verified customer-ready service or an independent AI bug reviewer.

The source review identified defects in scanner execution, secret normalization, revision attribution, GitHub triggering, authorization, and reporting. Cleanup does not fix those defects. Accepted design and implementation evidence are separate: the [managed-beta plan](docs/plans/2026-10-16-managed-beta-implementation-plan.md) records the work required before release.

## Start here

- [Local setup](RUNNING_LOCALLY.md): the single development setup guide.
- [Current implementation architecture](docs/SYSTEM_OVERVIEW.md): components, source entry points, integrations, and known gaps.
- [Domain vocabulary](CONTEXT.md): named concepts used in decisions and code.
- [Architecture decisions](docs/adr/): ADR-010 through ADR-017 define the accepted managed-beta direction; earlier ADRs preserve architectural rationale.
- [Accepted roadmap decisions and findings](docs/reviews/2026-10-16-roadmap-grilling.md): Q1–Q54, dispositions, and acceptance requirements.
- [Implementation plan](docs/plans/2026-10-16-managed-beta-implementation-plan.md): dependency-ordered M00–M15 tasks and evidence gates.
- [Cleanup decisions](docs/reviews/2026-10-16-cleanup-decisions.md): retained material and deletion accounting.

## Code and contracts

| Area | Source |
| --- | --- |
| Web pages and client | [apps/web/app](apps/web/app), [API client](apps/web/lib/api.ts) |
| API entry point and routes | [main.py](apps/api/app/main.py), [router.py](apps/api/app/api/v1/router.py) |
| Durable data | [models](apps/api/app/db/models), [migrations](apps/api/alembic/versions) |
| Worker and orchestration | [worker entry point](apps/worker/app/worker/main.py), [orchestrator](apps/worker/app/services/scan_orchestrator.py) |
| Scanners and normalization | [registry](apps/worker/app/scanners/registry.py), [normalizers](apps/worker/app/normalizers) |
| Generated API contracts | [OpenAPI](apps/api/openapi.json), [TypeScript types](apps/web/lib/api-types.ts) |
| Development commands | [Makefile](Makefile), [local infrastructure](docker-compose.yml) |
| Deployment artifacts | [infra](infra), [Render configuration](render.yaml) |

The Git repository root is the parent `scanforge` directory. Its [CI workflow](../.github/workflows/ci.yml) is outside this project directory. Generated OpenAPI and TypeScript contracts are checked-in implementation inputs; regenerate them when their sources change.

## Operations and retained evidence

The [operator runbooks](docs/runbooks) cover provisioning, credential rotation, organization disablement, recovery, backup/restore, verification, and incidents. Their existence does not establish that the corresponding deployment drills have passed.

September material remains for detailed policy and historical evidence accounting:

- [Readiness specification](spec/2026-09-13-evidence-first-readiness.md)
- [Evidence policy](spec/2026-09-13-scan-evidence-policy.md)
- [Evidence decisions](spec/2026-09-13-scan-evidence-decisions.md)
- [Historical readiness tracker and receipts](docs/plans/2026-09-13-evidence-first-readiness-plan.md)
- [Completion test boundary](docs/plans/r04-completion-test-boundary.md)
- [Local recovery drill evidence](docs/plans/r12-recovery-drill-runbook.md)

Where earlier scope or execution order conflicts, the accepted October decisions and plan govern. Historical test counts and local receipts are not current release verification.
