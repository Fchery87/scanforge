# Validation Tasks

Last scan: 2026-04-04
Profile: full
Validation Health Score: 76/100
Target Threshold: 95/100
Perfectionist State: no

## Summary

- Tech stack: Next.js 16, React 19, TypeScript, FastAPI, SQLAlchemy, Alembic, Python 3.12, Upstash Redis REST, Cloudflare R2/MinIO
- Commands executed:
  - `npm run lint` in `apps/web`: failed
  - `make lint`: failed
  - `make test`: passed
  - focused API regression test: passed
  - focused worker orchestrator tests: passed
- Blocking reasons:
  - frontend lint still has open errors
  - repo-wide lint still fails because frontend lint is now a real gate

## Task Table

| ID | Status | Severity | Category | Scope | Location | Summary |
| --- | --- | --- | --- | --- | --- | --- |
| TASK-001 | done | high | test | global | `apps/api/app/api/v1/routes/github.py` | Fixed invalid OAuth state regression to fail before unnecessary DB traversal |
| TASK-002 | done | high | test | global | `apps/worker/tests/test_scan_orchestrator.py` | Updated worker tests to match the current queue payload and scan context contract |
| TASK-003 | done | high | config | global | `apps/web/package.json`, `apps/web/eslint.config.mjs`, `Makefile` | Replaced broken `next lint` path and made validation targets fail on real errors |
| TASK-004 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx` | Remove unused `SkeletonStats` import |
| TASK-005 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx` | Resolve unused values, empty catch blocks, and missing react-hooks rule usage |
| TASK-006 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/ScheduleSection.tsx` | Remove unused `cn` import |
| TASK-007 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx` | Fix unused expression lint error |
| TASK-008 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx` | Remove unused values and replace empty blocks |
| TASK-009 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx` | Remove unused values and replace empty blocks |
| TASK-010 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/suppressions/page.tsx` | Replace empty blocks |
| TASK-011 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.tsx` | Remove unused `SkeletonCards` import |
| TASK-012 | todo | medium | lint | global | `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx` | Remove unused values and replace empty blocks |
| TASK-013 | todo | medium | lint | global | `apps/web/app/(dashboard)/notifications/page.tsx` | Remove unused values |
| TASK-014 | todo | medium | lint | global | `apps/web/app/(dashboard)/profile/page.tsx` | Remove unused `SkeletonList` import |
| TASK-015 | todo | medium | lint | global | `apps/web/components/scanforge/*`, `apps/web/components/ui/command.tsx`, `apps/web/hooks/use-toast.ts` | Clear remaining unused imports, no-empty-object-type, and similar ESLint findings |

## Task Details

### TASK-001
- Status: done
- Details: `github_oauth_callback` and `github_install_callback` now extract `org_id` from the signed state payload first, convert malformed state into a deterministic `400`, and only then perform organization lookups and permission checks.
- Suggested fix: none; completed.

### TASK-002
- Status: done
- Details: worker tests now provide `organization_id` in `ScanContext` and `org_id` in queued job payloads, matching the live orchestrator contract.
- Suggested fix: none; completed.

### TASK-003
- Status: done
- Details: web lint now runs through ESLint flat config and `make lint` and `make test` no longer swallow failures.
- Suggested fix: none; completed.

### TASK-004 through TASK-015
- Status: todo
- Details: the newly working frontend lint command surfaced 47 existing errors, mostly unused imports and variables, empty catch blocks, one unused expression, and one missing React Hooks lint plugin rule reference in code already present before this change.
- Suggested fix: clean these files in small batches, then rerun `npm run lint` and `make lint`.

## Scan History

- 2026-04-04 | profile=`full` | score=`76` | tests passed | lint failed | perfectionist=`false`
