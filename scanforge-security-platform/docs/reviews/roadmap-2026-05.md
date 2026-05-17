---
title: ScanForge — Strategic Review & Roadmap
date: 2026-05-16
weighting: 40% roadmap / 30% strategic / 30% engineering
status: working draft for prioritization
---

# ScanForge — Strategic Review & Roadmap (May 2026)

> **TL;DR.** ScanForge is a competent, multi-tenant **repository security operations platform** with a clean domain model, 7 wired deterministic scanners, and a mature workflow layer (RBAC, scorecards, audit logs, advisory PR feedback). Its closest commercial peer is **Aikido**; its closest open-source peer is **DefectDojo** (with the major distinction that ScanForge *runs* scanners, not just ingests them). Today it is *behind* the AI-native frontier set by `vercel-labs/deepsec`, Semgrep Multimodal, and Corgea — none of which have ScanForge's multi-tenant platform layer. **The wedge is "DefectDojo-class platform + deepsec-class investigation."** This document ranks the work needed to claim that wedge.

---

## Part 1 — Strategic Frame (30%)

### 1.1 What ScanForge actually is, today

ScanForge is a **hosted, multi-tenant repository-security control plane** with these pillars:

- **Inputs**: GitHub App webhooks, scheduled crons, manual scan requests; trigger one of four scan types (`scan.repo.full`, `scan.repo.diff`, `scan.dependencies`, `scan.secrets`).
- **Engine**: Python worker that clones the repo, runs 7 deterministic scanners in parallel (**Trivy, Gitleaks, OSV-Scanner, Semgrep, Syft, Checkov, Grype**), uploads raw artifacts to R2/MinIO, and normalizes each scanner's output to a canonical `Finding` shape.
- **State**: Neon Postgres via SQLAlchemy async. 15 entities with explicit lifecycle states (8 finding states: `open`, `reviewing`, `to_fix`, `accepted_risk`, `false_positive`, `duplicate`, `not_observed`, `fixed`). Append-only `FindingEvent` + `AuditLog`.
- **Surfacing**: Next.js 16 / React 19 dashboard with a triage table, finding drawer, scorecard, exports (CSV/JSON), notification center, audit log viewer.
- **Trust controls**: Neon Auth JWT + organization-scoped RBAC (owner / admin / security_reviewer / viewer), webhook HMAC + replay protection, Redis-backed rate limiting, sanitized error responses.

This is *substantially more product* than its 6-week commit history suggests — the domain model has been deliberately decoupled (per `ADR-003` and `ADR-004`), and the test suite (159 tests across API + worker) covers contracts, RBAC, lifecycle invariants, and normalizer output shape.

### 1.2 Use cases the current build can execute end-to-end today

1. **Org onboarding** — create org, invite members with roles, install GitHub App, add repositories.
2. **On-demand multi-scanner audit** — trigger full scan, watch per-scanner health, see deduplicated findings with risk scores and remediation guidance.
3. **Nightly scheduled scans with lifecycle automation** — auto-mark missing findings `not_observed`, auto-promote to `fixed` after N clean scans.
4. **Advisory PR feedback** — webhook diff scans (Semgrep + Gitleaks + Checkov on changed files) post a non-blocking PR comment with risk score + policy result.
5. **Triage workflow** — assign, set due dates, see SLA badges (overdue / due-soon / on-track), bulk transition state, write suppression rules.
6. **Reporting & audit** — org/project scorecards (exposure, trend, SLA pressure, scanner health), CSV/JSON exports with presigned download, full audit trail of every mutation.

### 1.3 Comparable products — where ScanForge sits

| Product | What it is | Where it beats ScanForge | Where ScanForge beats it |
|---|---|---|---|
| **vercel-labs/deepsec** | Open-source CLI security harness, AI-agent investigation (Claude Opus 4.7 / GPT 5.5 at max thinking), file-based storage, $$$$ per scan | Deep AI investigation, FP-revalidation step, plugin matchers, Vercel Sandbox microVMs, agent backends | Multi-tenant SaaS, persistent DB, RBAC, scheduled scans, 7-scanner breadth, dashboard, audit, cheap predictable cost |
| **Aikido Security** | Commercial unified AppSec (SAST+SCA+secrets+IaC+container+DAST) | AI Autofix, broader scanner mix, cloud/runtime/DAST, mature integrations | Open foundations, transparent risk formula, opinionated workflow states |
| **DefectDojo** | OSS vulnerability management (5K stars) — ingests reports, dedupes, triages | Mature deduplication, parser ecosystem (~150 scanners), wide install base | Runs the scanners itself, modern stack, real-time webhooks, advisory PR feedback |
| **Cycode** | Enterprise ASPM with "Risk Intelligence Graph" | Reachability, ownership mapping, AI native | Lower TCO, simpler model |
| **Corgea** | AI-first SAST with business-logic flaw detection | AI for hidden business-logic flaws, PR review agent | Platform breadth, multi-scanner aggregation |
| **Semgrep Pro + Multimodal** | SAST + Supply Chain with reachability + AI autofix in PR | Reachability analysis, Multimodal AI autofix, mature PR/MR triage by comment | Suite breadth (gitleaks/trivy/IaC), unified scorecards across scanners |
| **Snyk** | Incumbent, reachability + AI fixes | Brand, scale, IDE integration, reachability | Lower price point, less noisy default |
| **Dependency-Track** | SBOM/SCA-centric OSS | SBOM ecosystem (~150 integrations), VEX, EPSS | Multi-domain scanning, dashboard ergonomics |

**Positioning verdict:** ScanForge is best read as a *modernized, opinionated DefectDojo with built-in scanner orchestration*. That's a defensible niche, but it's a crowded one — Aikido already eats it commercially. The strategic question is whether ScanForge sits there or stakes a sharper claim.

### 1.4 Deep comparison: ScanForge vs. `vercel-labs/deepsec`

You explicitly asked for this comparison, so it gets its own treatment.

**deepsec, in one paragraph.** A 2K-star, MIT-licensed CLI tool from Vercel Labs (launched 2026-05-04). Runs locally or in a Vercel Sandbox microVM. Five-stage pipeline (`scan` → `process` → `revalidate` → `enrich` → `export`). The `scan` stage uses ~110 hand-built regex matchers to flag *candidate* files (cheap, ~15s on 2k files). The `process` stage runs each candidate through an AI coding agent (Claude Opus 4.7 default, GPT 5.5 alt, both at max reasoning) with project-specific `INFO.md` context — the agent reads the code, traces data flows, checks mitigations, emits structured findings. The `revalidate` stage runs the agent *again* on each finding to weed out false positives by re-reading the code and consulting git history; Vercel claims this cuts FP rate by 50%+. One file = one `FileRecord` JSON; pipeline is **append-only and resumable**; you can re-run with a different model/prompt and merge improvements rather than overwrite. Plugin architecture has 5 extension points (matchers, notifiers, agents, ownership, people directory, executor). No UI, no DB, no auth, no multi-tenancy — by design.

**ScanForge and deepsec are not direct competitors. They are *philosophically opposite* and *complementary*:**

| Dimension | deepsec | ScanForge |
|---|---|---|
| Deployment model | CLI in your CI / sandbox | Hosted multi-tenant SaaS |
| Primary user | Security engineer running a deep audit | Security team operating continuous program |
| Scan philosophy | AI agent investigates each candidate | Deterministic scanners produce findings |
| Cost per scan | "thousands to tens of thousands of dollars" for large repos | Pennies (subprocess + storage) |
| Persistence | `.deepsec/` directory (file JSON) in same repo | Postgres + S3 |
| FP handling | Active `revalidate` agent re-investigation | Lifecycle states (`false_positive` via human triage) |
| Multi-tenancy | None | First-class (org → project → repo) |
| Auth | None | Neon Auth JWT + RBAC |
| Plugin system | 5 extension points, 1st-class | Closed scanner registry |
| Resumability | First-class (per-file lock) | Best-effort (retry + DLQ) |
| Output | Markdown / JSON for ticket ingestion | Dashboard + REST + exports |

**Key things ScanForge can borrow from deepsec** (these become roadmap items in Part 3):

1. **AI investigation layer on top of deterministic findings.** Today ScanForge ships you the Trivy/Semgrep output, lightly enriched. deepsec proves there's serious value in running an agent over each candidate to trace flows and judge exploitability. ScanForge has the platform to make this *optional and per-finding* (e.g., "Investigate with AI" button), avoiding the $$$$ blanket cost.
2. **`revalidate` as a first-class concept.** ScanForge's `not_observed → fixed` automation is great for *scanner-derived* lifecycle, but deepsec's per-finding revalidation (was-it-fixed? still-exploitable? FP?) is a *separate signal* that ScanForge lacks.
3. **Plugin matchers / scanners.** deepsec's 5-extension-point model is best-in-class. ScanForge's scanner registry (`apps/worker/app/scanners/registry.py`) is closed; opening it lets customers add org-specific matchers (auth helpers, custom crypto patterns).
4. **Append-only analysis history.** ScanForge has `FindingEvent` for state transitions but not for *re-investigation*. deepsec's `analysisHistory[]` is cleaner for "this finding was re-scanned with a stronger model and severity changed."
5. **Sandbox execution.** ScanForge's worker is a bare Python process. Wrapping scanner execution in microVMs (Vercel Sandbox, Fly Machines, Firecracker) gives stronger isolation guarantees that matter for enterprise / regulated buyers.
6. **Tiered classification tiers.** deepsec splits `triage` (cheap P0/P1/P2 model) from `process` (full investigation). ScanForge has risk scoring but not a separate fast-pass classification — could be cheaper way to filter the long tail before deep analysis.

**Key things deepsec should borrow from ScanForge** (relevant because it sharpens differentiation):
- Multi-tenancy, RBAC, audit
- Persistent finding history beyond a single repo
- Scheduled / continuous scanning (deepsec is on-demand only)
- Webhook-driven CI scanning at PR time

### 1.5 The strategic fork

ScanForge has two viable directions. They are not mutually exclusive, but the order matters.

**Path A — "Beat Aikido at the workflow layer."** Keep deterministic scanners, double down on triage UX, scorecards, integrations (Jira, Slack, MS Teams, IDE), SSO, on-prem. *Risk: low differentiation against a well-funded incumbent.*

**Path B — "Open-source platform + optional AI deep-scan."** Be the only product that combines (a) DefectDojo-class multi-tenant platform + (b) deepsec-class agent investigation as an opt-in per-finding or per-repo feature, gated by spend caps. *This is the wedge.* Aikido has AI autofix but not AI investigation at the deepsec depth. Corgea has AI but no platform breadth. ScanForge can own the intersection.

**Recommendation: pursue Path B, but earn permission with Phase 0/1 of Path A first.** The investigation layer is only valuable on top of a stable platform.

---

## Part 2 — Engineering Critique (30%)

This section is intentionally brutal; specifics with file paths.

### 2.1 What's done well

1. **Domain ownership is codified.** `ADR-003-scan-lifecycle-architecture-program.md` and `ADR-004-finding-lifecycle-policy.md` are real architectural contracts, not after-the-fact rationalizations. Worker treats queue payloads as identity-only, loads authoritative context from API. Reduces drift.
2. **Workflow states as first-class.** Eight finding states (not overloaded "suppressed") with centralized transition logic in `apps/api/app/services/finding_lifecycle.py`. Risk-score multiplier per state (`fixed=0.0, accepted_risk=0.25, false_positive=0.15, …`) is the kind of detail that signals real product thinking.
3. **Risk scoring is transparent, not magic.** `apps/api/app/services/risk_scoring.py` — `base[severity] + confidence_bonus + importance_bonus) × state_multiplier`. Auditable, debuggable, defensible to a security buyer.
4. **Scanner health is a separate signal from scan status.** A scan can complete with partial scanner failures, and `not_observed → fixed` promotion only fires when the *relevant* scanner actually ran. This is the kind of subtle correctness that scales.
5. **Test discipline.** 119 API + 40 worker tests cover contracts (queue, normalizer output, webhook), policy logic (SLA, advisory policy, risk score), and access control (route auth regressions, RBAC). Strong foundation for safe refactoring.
6. **Webhook security.** HMAC verification + `WebhookDelivery.delivery_id` unique constraint for replay protection. GitHub OAuth state signed.
7. **Audit log on every mutation.** Tamper-evident operational history — table stakes for SOC2, present from day one.
8. **Async-first Python stack.** Asyncpg + SQLAlchemy async + httpx + worker async orchestration. Will scale to concurrent scanner runs without rewrite.

### 2.2 High-priority risks (fix before any new feature work)

1. **Frontend has zero automated test coverage.** No vitest/jest. `next lint` is broken (`apps/web/package.json`, `Makefile:140-147`). The findings UI is the most complex surface in the product — pagination, filters, bulk actions, drawer. Shipping it without a safety net is the single largest risk in the codebase.
2. **Validation targets swallow failures.** `make test` and `make lint` are invoked with `|| true` in primary Makefile targets (`Makefile` ~line 188). Local validation looks green when tests fail. This is unsafe as a CI gate and *must* be the first fix before adding GitHub Actions.
3. **No CI/CD pipeline.** No `.github/workflows/`. All quality gates depend on the developer remembering to run `make test` and `make lint`. With #2, even that is unreliable.
4. **OAuth callback authorization regression** (`apps/api/app/api/v1/routes/github.py:77-91` per audit). Route queries organization before state validation completes; a regression test exists but indicates contract drift. Security-sensitive path.
5. **Web app has no test infrastructure at all.** Beyond test absence, there's no `vitest.config.ts`, no test scripts, no testing-library setup. Adding tests requires bootstrapping the harness.

### 2.3 Medium-priority gaps

6. **No observability beyond logs.** No Prometheus/OTel/StatsD. No query profiling. No scan-duration histograms. Slow findings queries will be invisible until they page. Recommend OpenTelemetry instrumentation on scan execution, normalizer time, and HTTP handlers — exported to Grafana Cloud or similar.
7. **No artifact retention policy.** Scan artifacts are uploaded to R2 with no lifecycle rule and no cleanup job (`apps/worker/app/services/scan_orchestrator.py`). Storage costs grow unbounded. Easy fix: R2 lifecycle rule + per-org retention setting.
8. **No rate limiting on scan creation.** A user can spam `POST /api/v1/organizations/{org}/projects/{project}/scans`. Queue can be drowned. Add per-repo scan throttle (e.g., 1 / 5 min) at API layer.
9. **No pagination hard limit.** Findings/scans pagination accepts client-controlled page size with no max. Malicious or buggy client can request 1M results.
10. **Soft delete / GDPR readiness missing.** Deleting an org cascade-deletes everything. No archival, no anonymization path. Will be a problem for any enterprise deal.
11. **Normalizer edge cases under-tested.** Tests cover happy paths. No tests for empty scanner output, malformed JSON, scanner timeout. Silent zero-finding scans are a real risk.
12. **PR advisory is comment-only.** No GitHub Check-Runs API integration. Comments are noisy and easy to ignore. Check-Runs surface in the PR UI more naturally and unlock the path to blocking (when ready).
13. **Notification surface is thin.** SMTP + Slack webhook only. No digest mode, no per-user opt-in/out, no template customization.
14. **Documentation drift.** `docs/plans/` and `spec/` contain scaffold-era planning that contradicts current runtime. Concentrate active docs in `README.md`, `CONTEXT.md`, `docs/SYSTEM_OVERVIEW.md`, and `docs/adr/` — retire the rest.

### 2.4 Architecture observations (not bugs, but worth thinking about)

- **The 140KB `scan_orchestrator.py` is doing a lot.** Repo clone, scanner execution, artifact upload, normalization, finding persistence, notification dispatch — all in one orchestration layer. It's tested, but it's also the single largest blast radius. As you add an AI investigation step (Part 3), I'd factor this into pipeline stages with explicit handoff types, à la deepsec's `scan` / `process` / `revalidate` separation.
- **`internal/` routes are an anti-pattern over time.** Currently you have a clean split — public REST under `/api/v1/`, internal RPC under `/api/v1/internal/` with HMAC auth. As the worker grows, this surface will sprawl. Consider promoting the internal API to a separate gRPC service or at minimum versioning it independently.
- **No queue abstraction.** Upstash REST client is used directly (`apps/worker/app/services/queue_client.py` per the audit). Migration to SQS / Cloud Tasks / NATS later will require code changes, not config. A thin queue interface is cheap insurance.
- **Web client doesn't share types with API.** `packages/scanforge_contracts` is Python-only. Either generate TS types from OpenAPI (FastAPI emits it) or move to a polyglot contracts strategy (e.g., Protobuf, JSON Schema → both). Currently every API change risks breaking the frontend silently.

---

## Part 3 — Roadmap (40%, full backlog ranked by impact/effort)

> Format: **[Tier]** Item — *impact / effort* — rationale + file pointers where useful.
>
> **Tiers**: P0 = ship in next 2 weeks; P1 = next 4–6 weeks; P2 = next quarter; P3 = next 6 months; P4 = moonshot / strategic.

### Tier P0 — Stabilize the foundation (do before anything else)

| # | Item | Impact | Effort | Notes |
|---|---|---|---|---|
| 1 | **Remove `|| true` from `make test` / `make lint`** | High | 1 hr | Makefile ~L188. Validation must fail loudly. |
| 2 | **Wire GitHub Actions CI** (lint + tests on PR + main) | High | 1 day | Use Render-equivalent test commands. Block merges on failure. Don't promise more than tests + lint at first — observability + e2e come later. |
| 3 | **Fix OAuth callback validation order** | High (security) | 2 hr | `apps/api/app/api/v1/routes/github.py:77-91`. Validate state before org lookup. Update regression test. |
| 4 | **Replace broken `next lint` with direct ESLint invocation** | Medium | 1 hr | `apps/web/package.json`. `eslint . --max-warnings 0`. |
| 5 | **Add scan-creation rate limit** (per repo) | Medium (abuse) | 4 hr | `apps/api/app/api/v1/routes/scans.py`. Redis-backed, 1 scan / 5 min default. |
| 6 | **Hard pagination caps** (max 200/page on findings/scans) | Low | 2 hr | Defence-in-depth. |
| 7 | **Retire stale planning docs** | Low | 2 hr | Move `docs/plans/*` and obsolete `spec/*` to `docs/archive/`. Keep README, CONTEXT, SYSTEM_OVERVIEW, ADRs as source of truth. |

**P0 total: ~3 days of focused work.** Block all P1+ until done.

### Tier P1 — Table stakes parity (4–6 weeks)

| # | Item | Impact | Effort | Notes |
|---|---|---|---|---|
| 8 | **Bootstrap web test harness** (vitest + Testing Library) | High | 2 days | Cover findings table, filters, bulk actions, drawer state machine. Aim for 60% coverage on `components/scanforge/*`. |
| 9 | **Playwright e2e for happy paths** (login → org → scan → triage) | High | 3 days | Two tests is plenty: full scan flow + PR diff flow. Run nightly in CI, not on every PR. |
| 10 | **OpenTelemetry instrumentation** (FastAPI + worker) | High | 3 days | Export to Grafana Cloud free tier or Honeycomb. Spans on scan stages, normalizer runs, finding persistence. Critical before you scale. |
| 11 | **Generate TypeScript types from FastAPI OpenAPI** | Medium | 1 day | `openapi-typescript`. Drop into `apps/web/lib/api/types.ts`. Eliminates silent contract drift. |
| 12 | **R2 artifact lifecycle (90-day retention by default, per-org override)** | Medium | 1 day | Lifecycle rule + UI toggle in org settings. |
| 13 | **Slack notification template improvements** + **MS Teams webhook** + **per-user opt-in/out** | Medium | 4 days | `apps/api/app/services/notifications.py`. Add `NotificationPreference` table. |
| 14 | **GitHub Check-Runs integration** (in addition to PR comments) | High | 3 days | Better PR UX. Foundation for future blocking. |
| 15 | **Jira integration** (one-way push: finding → ticket) | High | 4 days | Top requested by security teams. Start one-way, add bidirectional later. |
| 16 | **Soft delete for org / project / repo** + 30-day grace period | Medium | 3 days | Adds `deleted_at` columns + nightly hard-delete job. Unblocks future GDPR work. |
| 17 | **Normalizer edge-case test suite** (empty / malformed / timeout per scanner) | Medium | 2 days | `apps/worker/tests/test_normalizers.py`. One test class per failure mode per scanner. |

### Tier P2 — Differentiation: the AI investigation layer (this quarter)

This is the strategic wedge. Build it on top of stable P0/P1 foundations.

| # | Item | Impact | Effort | Notes |
|---|---|---|---|---|
| 18 | **"Investigate with AI" per-finding action** | **Very high** | 2 weeks | Build agent loop using Claude Agent SDK (Opus 4.7). Input: finding + surrounding code + git blame + INFO.md (per-repo). Output: structured verdict (true-positive / false-positive / fixed / uncertain) + reasoning + suggested fix sketch. Cost-gated per org (monthly budget cap, per-finding cost estimate shown before run). Mirrors deepsec `process` + `revalidate` collapsed. |
| 19 | **Per-repo `INFO.md` ingestion** | High | 3 days | Read `INFO.md` from repo root (or org default in settings). Inject into AI investigation prompts. Steal the pattern verbatim from deepsec — it works. |
| 20 | **AI Autofix PRs** | High | 1 week | When finding has clear remediation (dependency upgrade, simple SAST), generate fix branch + PR. Start with SCA upgrades (cheap, deterministic), expand to SAST later. Match Semgrep Multimodal's pattern. |
| 21 | **Reachability analysis for SCA** (Python + JS to start) | Very high | 3+ weeks | Build with static call graph analysis (`pyan`, `madge`) or partner with an open library. Mark transitive vulns as "reachable" / "not reachable". This is Snyk's & Semgrep's biggest moat — closing it is a flagship feature. |
| 22 | **Plugin scanner registry** (`scanner.config.ts`-style) | High | 2 weeks | Open `apps/worker/app/scanners/registry.py` for customer-contributed adapters. Define ScannerAdapter contract, allow per-org scanner enablement, package as `@scanforge/scanner-foo`. Steal the 5-extension-point design from deepsec (matchers / normalizers / scanners / notifiers / ownership). |
| 23 | **Triage tier classification** (cheap pass before deep investigation) | Medium | 1 week | Run Haiku / cheaper model to classify findings P0/P1/P2 before AI investigation. Cuts cost on the long tail. |
| 24 | **Append-only investigation history** | Medium | 3 days | `FindingInvestigation` table. Each row = one agent run (model, prompt version, verdict, cost). Lets users re-investigate with stronger model and see how verdict changed. |

### Tier P3 — Scale to teams + early enterprise (3–6 months)

| # | Item | Impact | Effort | Notes |
|---|---|---|---|---|
| 25 | **GitLab + Bitbucket support** | High | 3+ weeks | Big door-opener. Mirror the GitHub App pattern; reuse the worker. |
| 26 | **SAML SSO + SCIM provisioning** | High (enterprise) | 2 weeks | Required for any deal over $20k ACV. Use WorkOS or Stytch to skip the SAML hell. |
| 27 | **Hard merge blocking via policy gates** | High | 2 weeks | Build on Check-Runs (#14). `Policy` table already exists (advisory). Promote to enforcing mode with org toggle. |
| 28 | **CLI (`scanforge`)** for local scans + CI ingestion | Medium | 2 weeks | `scanforge scan .` runs same scanners locally, uploads findings to your project. Lowers entry barrier; mirrors deepsec / Semgrep CLI ergonomics. |
| 29 | **Cost / spend dashboard** (AI investigation budget + R2 storage) | Medium | 1 week | Critical once #18 ships. Show per-org / per-project AI spend, monthly cap, kill-switch. |
| 30 | **IDE integration** (VS Code extension showing findings inline) | Medium | 3 weeks | Surface scan results in editor. Big "shift left" claim. |
| 31 | **EPSS + KEV enrichment** | Medium | 4 days | Pull EPSS scores + CISA KEV list, blend into risk score. Table stakes for security buyers. |
| 32 | **Audit log export** (S3 / Splunk / Datadog format) | Medium (compliance) | 4 days | Required for SOC2 customers. |
| 33 | **Vercel Sandbox / Firecracker execution** for scanner subprocess isolation | Medium | 2 weeks | Stronger security posture for regulated buyers. Pattern-match deepsec's sandbox mode. |
| 34 | **Cross-org findings deduplication** (when same lib has same CVE) | Medium | 2 weeks | Borrow DefectDojo's "Global Component Deduplication" idea. Cuts noise dramatically for multi-project orgs. |

### Tier P4 — Moonshot / strategic (6–12 months, only if Path B works)

| # | Item | Impact | Effort | Notes |
|---|---|---|---|---|
| 35 | **MCP server** for AI agents (Claude Code, Cursor, etc.) | High (positioning) | 2 weeks | Expose `list_findings`, `get_finding`, `triage_finding`, `request_investigation` over MCP. Becomes the "security context" for coding agents. Deferred per CONTEXT.md but the ecosystem is ready. |
| 36 | **deepsec compatibility mode** — ingest `.deepsec/data/` artifacts | Medium (community) | 1 week | Free flag-planting. Users running deepsec get a "send findings to ScanForge" path. |
| 37 | **Agent orchestration mode** — multi-agent investigation (different agents debate) | High (research) | 4+ weeks | Beyond what deepsec does. One agent investigates, second critiques, third validates. Costly but potentially state-of-the-art FP reduction. |
| 38 | **Self-hosted / on-prem distribution** (Helm chart + air-gapped install) | High (enterprise revenue) | 3+ weeks | Unlocks regulated industries. Worth it only if you've validated #25/#26/#27 with paying customers first. |
| 39 | **DAST / API security** | High | 6+ weeks | Big scope expansion. Likely only after AI-investigation differentiation is established. |
| 40 | **Runtime / CSPM integration** (read from AWS Config / GCP Asset Inventory) | High | 6+ weeks | Aikido's territory. Worth attacking only with a real engineering team. |

### 3.1 Recommended sequencing if I were planning your quarter

1. **Weeks 1–2**: All of P0. Non-negotiable. Frontend tests bootstrapped (item #8) starts in parallel.
2. **Weeks 3–6**: P1 items #8, #9, #10, #11, #14 (CI/observability/Check-Runs/types/tests). #12 + #16 + #17 in background.
3. **Weeks 7–10**: P2 item #18 (AI investigation MVP) end-to-end. Ship gated to a private beta.
4. **Weeks 11–13**: P2 #19 + #20 + #24 (INFO.md, AI Autofix for SCA, investigation history). Open beta.
5. **In parallel from week 6**: P1 #13 + #15 (notifications/Jira) — small dev can own.

Reachability (#21) and plugin scanners (#22) are bigger swings; defer to next quarter unless you have additional capacity.

### 3.2 What I'd *not* build, and why

- **A blockchain/SBOM provenance feature.** Hot in 2025; the buyers paying for it now (DoD / large finance) are not your ICP.
- **Generic vulnerability database / CVE browser.** OSV.dev exists, free, better-maintained.
- **In-product chat assistant.** Half-built AI chat is a tax. Earn the right to ship one by nailing the per-finding investigation first.
- **Mobile app.** Security platforms are tab-in-browser tools. No.
- **Multi-cloud support before GitLab support.** ICP signal is "we use GitHub + Slack" not "we use AWS + Azure + GCP." GitLab unlocks Europe + larger enterprises.

---

## Part 4 — Decisions This Document Forces

Three calls the team should make explicitly before executing:

1. **Path A or Path B?** Workflow incumbent (Aikido competitor) vs. AI-investigation differentiator. *My recommendation: B, earned after P0/P1.*
2. **Open core or closed?** deepsec is Apache 2.0, DefectDojo is BSD. The plugin scanner architecture (P2 #22) leans heavily toward open-core (community-contributed scanners). Decide now so license and contribution model are right.
3. **AI cost model?** Per-org monthly cap vs. per-scan credit pack vs. usage-based. Affects pricing page design and #18 implementation. Recommend a generous default cap + per-org override + clear pre-run cost estimate.

---

## Appendix A — Files most representative of current architecture

For onboarding a new contributor or auditing the codebase, these 20 files give the full shape:

**Domain core**
- `apps/api/app/db/models/finding.py`, `scan.py`, `repository.py` — central entities
- `apps/api/app/services/scan_lifecycle.py` — scan creation + enqueue (ADR-003 core)
- `apps/api/app/services/finding_lifecycle.py` — workflow states + transitions (ADR-004)
- `apps/api/app/services/findings.py` — finding persistence + deduplication
- `apps/api/app/services/risk_scoring.py` — risk score formula
- `apps/api/app/services/policy_evaluation.py` — advisory policy logic
- `apps/api/app/services/github_pr_advisory.py` — PR comment construction

**Worker / scanning**
- `apps/worker/app/worker/main.py` — entry point
- `apps/worker/app/services/scan_orchestrator.py` — orchestration (large; refactor candidate)
- `apps/worker/app/scanners/registry.py` — scanner adapter registration
- `apps/worker/app/scanners/base.py` — adapter interface
- `apps/worker/app/normalizers/*.py` — 7 normalizers

**Trust & access**
- `apps/api/app/middleware/auth.py` — Neon Auth JWT
- `apps/api/app/api/v1/routes/internal.py` — internal worker RPC
- `apps/api/app/api/v1/routes/github.py` — OAuth + webhooks (security-sensitive)

**Surface**
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- `apps/web/components/scanforge/findings-table.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.tsx`

**Contracts**
- `docs/adr/ADR-003-scan-lifecycle-architecture-program.md`
- `docs/adr/ADR-004-finding-lifecycle-policy.md`
- `README.md` + `CONTEXT.md` + `docs/SYSTEM_OVERVIEW.md` — active source of truth

## Appendix B — Sources consulted

- ScanForge codebase audit (15 entities, 14 migrations, 159 tests, 62 endpoints) — performed 2026-05-16
- `vercel-labs/deepsec` README and `docs/architecture.md` (commit on `main` 2026-05-08; v1.1.3)
- Vercel blog: "Introducing deepsec" (2026-05-04, Malte Ubl)
- Aikido Security platform overview (aikido.dev/platform)
- DefectDojo Documentation — Deduplication, Dependency-Track parser
- Dependency-Track v1.3 Finding Packaging Format spec
- Semgrep docs — comparisons vs. Snyk, Multimodal overview, autofix/PR triage
- Snyk reachability analysis docs
- Industry survey: Cycode, Corgea, Codephreak, Precogs, Aptori, Xygeni (market context)
