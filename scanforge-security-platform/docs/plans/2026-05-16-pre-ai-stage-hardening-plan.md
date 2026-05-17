# Pre-AI-Stage Hardening Plan

**Date:** 2026-05-16
**Goal:** Land the foundational quality gates, security tooling, and orchestrator structure required before the AI investigation stage can be built safely.
**Sequencing rule:** Each PR must be green on `main` before the next begins.

---

## 0. Context

The audit that triggered this plan (`docs/reviews/`) flagged 14 items. Verification against the actual codebase reduced the verified-active list materially:

| Finding | Verdict |
|---|---|
| #1 No frontend test coverage | Partial — 10 `node:test` files exist but no real component tests |
| #2 `make test` / `make lint` use `\|\| true` | **FALSE** — no suppression in `Makefile:188-195` |
| #3 No CI/CD | TRUE |
| #4 OAuth callback authz regression | **FALSE** — `verify_github_state` runs before `org_service.get_by_id` (`apps/api/app/api/v1/routes/github.py:92` then `:96`) |
| #5 No web test infrastructure | Partial — `node:test` used; no vitest/RTL/jsdom |
| #6 No observability | TRUE — no prometheus/otel/statsd |
| #7 No artifact retention | TRUE |
| #8 No rate limiting | TRUE |
| #9 No pagination hard limit | **FALSE** — `PaginationParams.limit` capped at `le=100` (`apps/api/app/schemas/common.py:12`) |
| #10 No soft delete / GDPR | TRUE |
| #11 Normalizer edge cases under-tested | Needs deeper read (190 LoC in `test_normalizers.py`) |
| #12 PR advisory is comment-only | TRUE |
| Arch: `scan_orchestrator.py` "140KB" | **Wrong** — actually 23KB / 599 lines |
| Arch: no queue abstraction | Partial — `apps/worker/app/clients/queue.py` exists, just not swappable |
| Arch: web doesn't share types with API | TRUE — `packages/contracts/` is empty README, `scanforge_contracts/` is Python-only |

Next product milestone: **AI investigation stage** between normalization and finding persistence. This plan delivers the prerequisites.

OWASP alignment target: **Top 10:2025** (broken access control, security misconfiguration, software supply chain failures, cryptographic failures, injection, insecure design, authentication failures, software & data integrity failures, security logging & alerting failures, mishandling of exceptional conditions).

---

## 1. Tool selections and rationale

| Concern | Tool | Why not alternative |
|---|---|---|
| Web test framework | Vitest + @testing-library/react + jsdom | `node:test` lacks DOM; Jest is heavier and slower; Next.js docs explicitly support Vitest |
| Lint debt | `ruff --fix` (safe only) + hand-fix | `--unsafe-fixes` can change semantics; `PLR2004` constant extraction wants thoughtful naming |
| Dependency updates | **Renovate** (primary) + Dependabot (GitHub Actions only) | Renovate's `minimumReleaseAge: 7` catches xz-style supply chain attacks; better grouping for monorepo; native pip + npm + Docker support. Dependabot retained only for GitHub Actions where it's purpose-built |
| Python vuln scan | `pip-audit` | uv audit requires migration to uv (out of scope); pip-audit works against current pip+venv setup |
| SBOM | `anchore/sbom-action` → CycloneDX | One-line YAML; OWASP recommends CycloneDX for security focus; defer Cosign/SLSA until tagged releases exist |
| Rate limiting | `fastapi-limiter` (original, not fork) | Uses pyrate-limiter v4; backs onto existing Upstash Redis; per-route dependency model fits ScanForge usage |
| Error tracking / alerting | **Structured JSON logs + Slack webhook handler** | No new SaaS subscription per project policy. Reuses existing Slack webhook (finding #13). GlitchTip self-hosted documented as future step if/when logs+Slack outgrow themselves |
| TS types from API | `openapi-typescript` (types only) + hand-written Zod schemas at fetch boundary | Hey API is 0.x with 15 breaking changes per release — too much churn for one engineer; openapi-typescript is stable types-only |
| Orchestrator structure | 3 stages with mutable `ScanContext` handoff | No pipeline framework — premature; mutable context lets future re-scan stages append without changing signatures |

---

## 2. PR sequence

Each PR section lists scope, acceptance criteria, and OWASP coverage.

---

### PR 0 — R2 lifecycle rule (standalone)

**Why first:** stops the storage meter immediately; touches infra not code, so no dependency on later PRs.

**Scope:**
- Add R2 lifecycle rule in `infra/` (Terraform or Cloudflare console) deleting scan artifacts older than N days (recommend 90 days as default; per-org retention setting deferred).
- Document the chosen retention in `docs/SYSTEM_OVERVIEW.md`.

**Acceptance:**
- Lifecycle rule visible in Cloudflare R2 console for the scan-artifacts bucket.
- `docs/SYSTEM_OVERVIEW.md` mentions retention.

**OWASP coverage:** none direct (operational concern).

---

### PR 1 — Lint cleanup

**Why second:** CI in PR 2 needs a green baseline. Current state: 89 lint errors (API ruff 34, Worker ruff 8, Web eslint 47).

**Scope:**
- `apps/api/.venv/bin/ruff check apps/api/app --fix` (safe fixes only)
- `apps/worker/.venv/bin/ruff check apps/worker/app --fix` (safe fixes only)
- `cd apps/web && npx eslint . --fix` (safe fixes only)
- Hand-fix remaining errors:
  - `PLR2004` magic numbers → extract to named constants (e.g. `SLA_DUE_SOON_DAYS = 3` in `apps/api/app/services/sla_policy.py`)
  - `E402` module-level imports → restructure or add `# noqa: E402` with justification comment if env loading must happen first
  - Unused imports/vars → delete (do not rename with `_` prefix unless the value is genuinely needed)
  - `no-empty-object-type` in `apps/web/components/ui/command.tsx` → either add a real member or remove the interface
- Land directly to `main` (no CI yet to gate).

**Acceptance:**
- `make lint` exits 0
- `make test` still exits 0 (no behavioral regressions)

**OWASP coverage:** A02 Security Misconfiguration (partial — cleans signal so CI can enforce going forward).

---

### PR 2 — CI workflow + supply-chain gates + web test harness

**Scope:**

**A. `.github/workflows/ci.yml`** — single workflow file with path-filtered jobs:

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
      worker: ${{ steps.filter.outputs.worker }}
      web: ${{ steps.filter.outputs.web }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'apps/api/**'
              - 'packages/scanforge_contracts/**'
              - '.github/workflows/ci.yml'
            worker:
              - 'apps/worker/**'
              - 'packages/scanforge_contracts/**'
              - '.github/workflows/ci.yml'
            web:
              - 'apps/web/**'
              - '.github/workflows/ci.yml'

  api:
    needs: changes
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -e "apps/api[dev]"
      - run: ruff check apps/api/app
      - run: PYTHONPATH=apps/api pytest apps/api
      - run: pip-audit --requirement <(pip freeze)

  worker:
    needs: changes
    if: needs.changes.outputs.worker == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -e "apps/worker[dev]"
      - run: ruff check apps/worker/app
      - run: PYTHONPATH=apps/worker pytest apps/worker
      - run: pip-audit --requirement <(pip freeze)

  web:
    needs: changes
    if: needs.changes.outputs.web == 'true'
    runs-on: ubuntu-latest
    env:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
      NEXT_PUBLIC_NEON_AUTH_BASE_URL: http://localhost:8000
      NEON_AUTH_BASE_URL: http://localhost:8000
      NEON_AUTH_COOKIE_SECRET: ci-dummy-secret-not-used-at-runtime
      NEON_AUTH_ISSUER: http://localhost:8000
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - run: cd apps/web && npm ci
      - run: cd apps/web && npm run lint
      - run: cd apps/web && npm audit --audit-level=high
      - run: cd apps/web && npx vitest run
      - run: cd apps/web && npm run build

  sbom:
    needs: changes
    if: needs.changes.outputs.api == 'true' || needs.changes.outputs.worker == 'true' || needs.changes.outputs.web == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anchore/sbom-action@v0
        with:
          path: .
          format: cyclonedx-json
          output-file: sbom.cyclonedx.json
          upload-artifact: true
```

**B. Vitest harness** (`apps/web/vitest.config.ts`):

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    include: [
      '**/*.test.ts',
      '**/*.test.tsx',
    ],
    exclude: ['node_modules', '.next'],
  },
})
```

`apps/web/vitest.setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())
```

New dev dependencies:
```
vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event vite-tsconfig-paths
```

Add to `apps/web/package.json` scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.

**Note:** Existing `node:test` files will continue to work — Vitest's `include` pattern covers them and Vitest supports `node:test`-style imports.

**C. Canary findings-drawer test** (`apps/web/components/findings/findings-drawer.test.tsx`):

One real component test asserting the drawer renders given a finding fixture and the severity badge color matches. Proves the harness works end-to-end.

**D. Renovate config** (`renovate.json` at repo root):

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "minimumReleaseAge": "7 days",
  "internalChecksFilter": "strict",
  "packageRules": [
    {
      "matchManagers": ["pip_requirements", "pep621", "npm"],
      "matchUpdateTypes": ["patch"],
      "automerge": true,
      "minimumReleaseAge": "14 days"
    },
    {
      "matchManagers": ["pip_requirements", "pep621", "npm"],
      "matchUpdateTypes": ["minor", "major"],
      "automerge": false
    },
    {
      "matchPackageNames": ["next", "react", "react-dom", "fastapi", "pydantic", "sqlalchemy"],
      "matchUpdateTypes": ["major"],
      "addLabels": ["framework-major-bump", "needs-review"]
    }
  ],
  "vulnerabilityAlerts": {
    "minimumReleaseAge": "0 days",
    "automerge": false,
    "addLabels": ["security"]
  }
}
```

**E. Dependabot for GitHub Actions only** (`.github/dependabot.yml`):

```yaml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

**F. Branch protection** (configured in GitHub UI after PR 2 lands green):
- Require `ci` checks to pass before merge
- Allow admin bypass (one-person team; emergency hatch)
- Require linear history

**Acceptance:**
- PR 2 itself shows the `ci` check green
- After merge, `main` shows the `ci` check green
- Renovate opens its first PRs within 24 hours (onboarding PR + any pending updates with `minimumReleaseAge` already satisfied)
- SBOM downloadable from latest workflow run as `sbom.cyclonedx.json`

**OWASP coverage:**
- **A02 Security Misconfiguration** — CI gate enforces correct config going forward
- **A03 Software Supply Chain Failures** — Renovate with `minimumReleaseAge`, pip-audit, npm audit, SBOM generation

---

### PR 3 — Orchestrator decomposition + structured logging + Slack alerting

**Scope:**

**A. Decompose `apps/worker/app/services/scan_orchestrator.py` into three stages:**

```
apps/worker/app/services/scan_pipeline/
  __init__.py
  context.py        # ScanContext (mutable handoff object)
  execution.py      # ScanExecutionStage (clone + scanner runs + artifact upload)
  normalization.py  # NormalizationStage (raw → canonical findings)
  persistence.py    # PersistenceStage (findings + notifications)
```

`ScanContext` is a mutable dataclass that each stage reads from and appends to. Each stage exposes `async def run(ctx: ScanContext) -> None`. The existing `ScanOrchestrator` becomes a thin coordinator that runs stages in order and handles top-level error reporting.

**Existing tests must continue to pass unchanged.** The 599-line `scan_orchestrator.py` has full test coverage; this is a refactor, not a rewrite. If a test breaks, the refactor is wrong.

**B. Structured JSON logs** — adopt `structlog` (or stdlib `logging` with a JSON formatter):

- Every log line carries `scan_id`, `org_id`, `project_id`, `request_id` (when available) as structured fields
- Each pipeline stage logs `stage_start` / `stage_end` / `stage_error` events with duration
- Replace any `print()` or unstructured logging in the orchestrator path

**C. Slack alert handler** — Python `logging.Handler` subclass that POSTs `ERROR`/`CRITICAL` records to the existing Slack webhook URL (already configured for notifications). Attached to the root logger in worker and API startup.

**D. Document the new stage layout in `docs/SYSTEM_OVERVIEW.md`** so the AI stage (PR 5) has a clear insertion point.

**Acceptance:**
- All existing worker tests pass unchanged
- New unit tests for each stage (input context → expected mutations)
- Manual smoke: trigger a scan locally, verify Slack receives an alert when an error is raised
- Log output is valid JSON parseable by `jq`

**OWASP coverage:**
- **A09 Security Logging & Alerting Failures** — structured logs + working alert path

---

### PR 4 — Rate limiting on sensitive endpoints

**Scope:**

Install `fastapi-limiter` (original `long2ice/fastapi-limiter`, NOT the `ab-fastapi-limiter` fork — we use per-route dependencies, not middleware).

Wire it up in `apps/api/app/main.py` startup to connect to existing Upstash Redis (reuse the connection config from worker's `QueueClient`).

Apply `RateLimiter` dependencies to:
- `POST /api/v1/organizations/{org_id}/projects/{project_id}/scans` — 1 scan per 5 minutes per (user, project)
- `POST /api/v1/github/oauth/callback` — 10 attempts per minute per IP
- `POST /api/v1/github/install/callback` — same
- Any login/auth-adjacent endpoint exposed by Neon Auth integration — 20 per minute per IP

429 responses must use the generic error message constant (no internal detail leakage — see PR 7).

**Acceptance:**
- New API tests: confirm 429 returned after threshold, confirm reset after window
- Manual smoke: spam-create scans, verify 429 after the second
- Confirm Redis keys cleaned up after TTL

**OWASP coverage:**
- **A07 Authentication Failures** — throttles credential-stuffing and OAuth-callback flooding
- **A04 Cryptographic Failures** (indirect — slows brute-force against any token-validation paths)

---

### PR 5 — AI investigation stage

**Scope:** (Deliberately under-specified here; this PR has its own design phase.)

- Insert a new `AIInvestigationStage` between `NormalizationStage` and `PersistenceStage` in the pipeline created in PR 3.
- Input: list of canonical findings from normalization.
- Output: each finding annotated with an AI-generated explanation and (optionally) a suggested remediation snippet.
- Model selection, prompt design, cost guardrails, retry policy, and prompt-injection defenses are all PR-5-internal decisions.
- Logging: token counts, model identifier, latency per finding — emitted as structured log events so future observability work has data to chart.

**Acceptance criteria for PR 5 will be defined in its own design doc.** This plan only commits to the *slot* in the pipeline.

**OWASP coverage:** none direct (this is the feature being added; security review of the AI stage is its own scope).

---

### PR 6 — TS types from OpenAPI + Zod runtime validation

**Scope:**

**A. Emit OpenAPI from API:**
- Add a script `apps/api/scripts/emit_openapi.py` that imports the FastAPI app and writes `apps/api/openapi.json`
- Commit `openapi.json`
- Add a CI step to the `api` job: after tests pass, run the emit script and fail if `git diff --exit-code apps/api/openapi.json` is non-empty (forces commits to include the spec change)

**B. Generate TS types:**
- Add `openapi-typescript` dev dep to `apps/web`
- Add npm script: `"gen:types": "openapi-typescript ../api/openapi.json -o lib/api-types.ts"`
- Commit generated `apps/web/lib/api-types.ts`
- Add CI step to `web` job: run `npm run gen:types`, fail if `git diff --exit-code` is non-empty

**C. Zod schemas at fetch boundary:**
- Create `apps/web/lib/api-schemas.ts` with `z.object()` schemas for each API response actually consumed by the frontend
- Update fetch wrappers to call `.parse()` on responses
- On Zod failure: log to console + send structured error event (no Sentry — log only)

**Acceptance:**
- Hand-edit a Pydantic model in API → CI fails because `openapi.json` wasn't regenerated
- Hand-edit `openapi.json` → CI fails because `api-types.ts` wasn't regenerated
- Web compile-time error appears when a consumed endpoint's shape changes

**OWASP coverage:**
- **A08 Software & Data Integrity Failures** — runtime validation prevents the frontend from operating on malformed API responses

---

### PR 7 — Exception handler audit pass

**Scope:**

- `grep -rn "except Exception" apps/api/app apps/worker/app`
- For each catch:
  - Confirm a sanitized response is returned (use the existing `GENERIC_EXTERNAL_SERVICE_ERROR` constant pattern from `apps/api/app/core/error_messages.py`)
  - Confirm the original exception is logged at `ERROR` level with full context (via PR 3's structured logger)
  - Confirm no stack trace or internal field name leaks into the HTTP response body or the Slack alert text

- Add a regression test pattern (one per route file) asserting the 5xx response body contains no internal identifier (no SQL keyword, no file path, no exception class name)

- Add a CI lint rule (custom ruff plugin or grep step) banning bare `except:` and `except Exception` without a `logger.error(..., exc_info=True)` in the same block. The rule should be advisory-only initially (warning) and promoted to blocking after one cleanup pass.

**Acceptance:**
- Audit pass results documented in a short `docs/reviews/2026-MM-DD-exception-handler-audit.md` listing files reviewed and any changes made
- New regression tests pass
- CI grep step in place

**OWASP coverage:**
- **A10 Mishandling of Exceptional Conditions** (new category in 2025)

---

### PR 8 — Documentation cleanup

**Scope:**

- Audit `docs/plans/` — many entries pre-date current runtime. Move stale items to `docs/plans/archive/` with a header note explaining what shipped.
- Audit `spec/` directory — if contents are no longer authoritative, either update or archive
- Consolidate active architecture docs into the existing canonical set:
  - `README.md`
  - `CONTEXT.md`
  - `docs/SYSTEM_OVERVIEW.md`
  - `docs/adr/`
- Update `docs/SYSTEM_OVERVIEW.md` to reflect the post-PR-3 pipeline structure
- Add a `docs/adr/` entry for each architectural decision made in this plan (Renovate over Dependabot; openapi-typescript over Hey API; Slack-webhook alerts over Sentry; 3-stage orchestrator)

**Acceptance:**
- `docs/plans/` contains only forward-looking documents
- No active doc contradicts current runtime
- ADRs exist for the load-bearing tool choices

**OWASP coverage:** none direct.

---

## 3. Items deferred (and why)

| Item | When to revisit |
|---|---|
| Soft delete / GDPR data export | When an enterprise prospect's checklist requires it. Building speculatively wastes effort because compliance work is shaped by the customer's spec. |
| PR Check-Runs API (replacing comment-based advisory) | When (a) a user complains about comment noise, or (b) "block PR on critical finding" lands on the roadmap. Estimated 1-2 days of GitHub App permission work + webhook handler. |
| Full OpenTelemetry / Prometheus / Grafana stack | When structured logs + Slack alerts (PR 3) become insufficient for performance debugging. Symptom: you can't answer "where is scan time going" from log inspection alone. |
| GlitchTip self-hosted error tracking | When error volume makes Slack notifications unreadable, or you need stack-trace deduplication and grouping. Single Docker container, ~1GB RAM, MIT license, drop-in for Sentry SDK protocol. |
| Migration from pip+venv to uv | Quality-of-life PR worth doing eventually (~10x faster CI installs, `uv audit`, lockfile hygiene). Not on this plan's critical path. |
| Cosign signing + SLSA provenance for SBOMs | When you start cutting tagged releases. Currently no version tags in git history. |
| Per-org artifact retention setting | When a customer or finance team asks. Default-90-days from PR 0 covers the cost concern. |
| Polyglot contracts (Protobuf, JSON Schema) | When you have a second non-TS client. Single-client codegen (PR 6) is sufficient now. |
| `next lint` repair (audit's claim that it's broken) | Verify in PR 1 — `apps/web/package.json` runs `eslint . --max-warnings 0`, not `next lint`. May already be a non-issue. |

---

## 4. OWASP Top 10:2025 coverage summary

| Category | Addressed in |
|---|---|
| A01 Broken Access Control | Already correct in `apps/api/app/api/v1/routes/github.py:92` (verified, not regressed). No PR needed. |
| A02 Security Misconfiguration | PR 1 (lint cleanup) + PR 2 (CI gate) |
| A03 Software Supply Chain Failures | PR 2 (Renovate `minimumReleaseAge`, pip-audit, npm audit, SBOM) |
| A04 Cryptographic Failures | Existing Neon Auth handles primary cryptography; PR 4 indirect (rate limiting slows brute-force) |
| A05 Injection | Existing — SQLAlchemy parameterized queries throughout; no new work |
| A06 Insecure Design | Existing — covered by ADRs in `docs/adr/`; PR 8 reinforces |
| A07 Authentication Failures | PR 4 (rate-limit auth/OAuth endpoints) |
| A08 Software & Data Integrity Failures | PR 6 (Zod runtime validation at fetch boundary) |
| A09 Security Logging & Alerting Failures | PR 3 (structured logs + Slack alert handler) |
| A10 Mishandling of Exceptional Conditions | PR 7 (exception handler audit + CI lint rule) |

---

## 5. Verified-false items (no work needed)

The audit flagged these. Verification showed they don't exist as described. Documented here so the next person reading the audit doesn't re-investigate.

| Audit claim | Verified state |
|---|---|
| `make test` / `make lint` use `\|\| true` | False — `Makefile:188-195` runs both with no suppression |
| OAuth callback queries org before state validation | False — `apps/api/app/api/v1/routes/github.py:92` (`verify_github_state`) runs before line 96 (`org_service.get_by_id`) |
| No pagination hard limit | False — `apps/api/app/schemas/common.py:12` already enforces `le=100` |
| `scan_orchestrator.py` is 140KB | False — actually 23KB / 599 lines |
| Frontend has zero test coverage | Partial — 10 `node:test` files exist; PR 2 adds the real component test harness |
| No queue abstraction | Partial — `apps/worker/app/clients/queue.py` exists as a class, just not swappable |

---

## 6. Open questions for PR-5 design (not for this plan)

These are deliberately out of scope here. Capture so the PR 5 design phase doesn't start cold.

- Model selection: Claude vs OpenAI vs both behind an interface
- Cost guardrails: per-scan token budget, per-org monthly budget
- Prompt-injection defenses: scanner output is untrusted; structured-extraction pattern needed
- Caching: identical finding fingerprints across scans should reuse prior investigations
- Failure mode: AI stage errors must not block scan completion (finding persists with no AI annotation)
- Privacy: customer code snippets sent to third-party model — disclosure and per-org opt-out
