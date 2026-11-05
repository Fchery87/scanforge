# ScanForge

ScanForge is a pre-release repository security scanner being directed toward developer-first, evidence-backed pull-request security review ([ADR-018](docs/adr/ADR-018-developer-first-security-review-direction.md)). The implementation contains a Next.js application, FastAPI API, PostgreSQL models and migrations, a durable scan dispatcher, and a Python scanning worker that runs seven open-source scanners in contained, network-disabled containers. It is not yet a verified customer-ready service, and it does not yet review pull requests.

## Documentation index

This file is the only documentation index. Read in this order:

| Topic | Authoritative document |
| --- | --- |
| Product direction | [Product charter](docs/PRODUCT_CHARTER.md) |
| Accepted decisions | [ADRs](docs/adr/): ADR-018 sets direction; ADR-010–017 define evidence, identity, dispatch, isolation and AI boundaries; ADR-001–009 preserve earlier rationale |
| Current architecture, trust boundaries, supported capabilities, known gaps | [System overview](docs/SYSTEM_OVERVIEW.md) |
| Implementation priorities | [Redirection implementation plan](docs/plans/2026-11-04-redirection-implementation-plan.md) (the single active plan) |
| Domain vocabulary | [CONTEXT.md](CONTEXT.md) |
| Local setup | [RUNNING_LOCALLY.md](RUNNING_LOCALLY.md) (the single setup guide) |
| Operator procedures | [Runbooks](docs/runbooks) |
| Agent conventions | [docs/agents](docs/agents) (issue tracker, triage labels, domain-doc rules) |
| Decision records and cleanup reports | [docs/reviews](docs/reviews): the October roadmap decisions (Q1–Q54) and the cleanup reports |
| History (non-authoritative) | [docs/archive](docs/archive/README.md) |

Where documents conflict: accepted ADRs govern until a newer ADR changes them; the charter sets direction; the active plan sets execution order. Nothing under `docs/archive/` is authoritative.

## Code and contracts

| Area | Source |
| --- | --- |
| Web pages and client | [apps/web/app](apps/web/app), [API client](apps/web/lib/api.ts) |
| API entry point and routes | [main.py](apps/api/app/main.py), [router.py](apps/api/app/api/v1/router.py) |
| Capability policy | [beta_capabilities.py](apps/api/app/core/beta_capabilities.py) |
| Durable data | [models](apps/api/app/db/models), [migrations](apps/api/alembic/versions) |
| Dispatch | [scan_dispatch.py](apps/api/app/services/scan_dispatch.py), [dispatch_main.py](apps/api/app/dispatch_main.py) |
| Worker and orchestration | [worker entry point](apps/worker/app/worker/main.py), [orchestrator](apps/worker/app/services/scan_orchestrator.py) |
| Scanners and normalization | [registry](apps/worker/app/scanners/registry.py), [normalizers](apps/worker/app/normalizers) |
| Generated API contracts | [OpenAPI](apps/api/openapi.json), [TypeScript types](apps/web/lib/api-types.ts) |
| Development commands | [Makefile](Makefile), [local infrastructure](docker-compose.yml) |
| Deployment artifacts | [infra](infra), [Render configuration](render.yaml) |

The Git repository root is the parent `scanforge` directory. Its CI workflow (`../.github/workflows/ci.yml`) is outside this project directory. Generated OpenAPI and TypeScript contracts are checked-in implementation inputs; regenerate them when their sources change.

## Evidence

The runbooks' existence does not establish that deployment drills have passed. Historical test counts and receipts in the archive are not current release verification. Ignored local evidence logs under `docs/reviews/readiness-2026-09-30/` are retained uncommitted.
