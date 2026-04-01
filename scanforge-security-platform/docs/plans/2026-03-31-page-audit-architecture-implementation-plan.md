# ScanForge Page Audit Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the page audit into a staged implementation program that improves activation, triage speed, governance safety, and scan-operations clarity across the highest-value ScanForge pages first.

**Architecture:** Build shared page infrastructure first, then deliver the top five ROI surfaces in dependency order: Findings, Organization Settings, Onboarding, Scan Detail/Operations, and Suppressions. Keep page-specific logic thin by extracting data-shaping, filter-state, action-policy, and governance helpers into `apps/web/lib`, and standardize UX around reusable `components/scanforge` primitives rather than embedding more route-local state machines directly inside page files.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, existing `node:test` unit tests, Next build/lint verification, existing ScanForge UI components, existing `api` client in `apps/web/lib/api.ts`

---

## Delivery Order

1. **Foundation:** route contracts, shared page patterns, page-level test coverage, and API-client normalization.
2. **ROI Slice 1:** Findings workspace.
3. **ROI Slice 2:** Organization settings and governance.
4. **ROI Slice 3:** Onboarding activation flow.
5. **ROI Slice 4:** Scan detail and scan operations.
6. **ROI Slice 5:** Suppressions governance.
7. **Tier 2 Pages:** repositories, project/org dashboards, scorecard, exports, notifications, profile, audit log.
8. **Tier 3 Pages:** root redirect and auth/account shells.

---

## Architectural Rules

- Keep route files focused on orchestration and composition only.
- Move data shaping, filter serialization, guardrail logic, and action policies into `apps/web/lib/**`.
- Prefer shared components under `apps/web/components/scanforge/**` over route-local one-offs.
- Add tests for every new helper module with `node:test`.
- Verify every page-surface change with `npm run build` and relevant `node --test` commands.
- Do not add feature flags unless a rollout risk is concrete.

---

### Task 1: Establish the Page Infrastructure Layer

**Why first:** The audited pages repeat the same problems: route-local fetch orchestration, ad hoc empty/error states, and inconsistent action handling. Fixing that once reduces cost everywhere else.

**Files:**
- Create: `apps/web/lib/page-surface/page-state.ts`
- Create: `apps/web/lib/page-surface/page-state.test.ts`
- Create: `apps/web/lib/page-surface/action-policy.ts`
- Create: `apps/web/lib/page-surface/action-policy.test.ts`
- Create: `apps/web/components/scanforge/page-state-panel.tsx`
- Modify: `apps/web/components/scanforge/empty-state.tsx`
- Modify: `apps/web/components/scanforge/page-header.tsx`

**Step 1: Write the failing test for page-state normalization**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { derivePageState } from "./page-state.ts";

test("prefers explicit error over empty and ready states", () => {
  assert.deepEqual(
    derivePageState({ loading: false, error: "Failed", itemCount: 0 }),
    { kind: "error", message: "Failed" }
  );
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/page-surface/page-state.test.ts`
Expected: FAIL because `page-state.ts` does not exist yet.

**Step 3: Write minimal implementation**

Implement `derivePageState`, `deriveActionAvailability`, and shared action guard helpers for destructive actions, unavailable integrations, and empty-data states.

**Step 4: Add a shared page-state panel component**

Create a reusable component that renders loading, empty, unavailable, and retry states with consistent copy and CTA slots.

**Step 5: Run tests and build**

Run: `cd apps/web && node --test lib/page-surface/page-state.test.ts lib/page-surface/action-policy.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/web/lib/page-surface apps/web/components/scanforge/page-state-panel.tsx apps/web/components/scanforge/empty-state.tsx apps/web/components/scanforge/page-header.tsx
git commit -m "feat(web): add shared page surface state infrastructure"
```

---

### Task 2: Normalize Page-Level API Adapters

**Why first:** Findings, onboarding, settings, scans, and suppressions all depend on richer route contracts than the current pages express locally.

**Files:**
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/lib/page-surface/contracts.ts`
- Create: `apps/web/lib/page-surface/contracts.test.ts`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx`

**Step 1: Write the failing contract test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { normalizeGithubIntegrationState } from "./contracts.ts";

test("maps absent github integration to disconnected state", () => {
  assert.equal(normalizeGithubIntegrationState(null).status, "disconnected");
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/page-surface/contracts.test.ts`
Expected: FAIL because the contracts module does not exist yet.

**Step 3: Implement thin contract-normalizer helpers**

Add helpers for:
- GitHub integration state
- invitation/member states
- onboarding completion/next actions
- scan lifecycle summaries
- suppression lifecycle summaries

**Step 4: Replace inline route conditionals with contract helpers**

Update the three seed pages above to consume the helpers instead of scattering `null`/`catch` behavior throughout the component body.

**Step 5: Run tests and build**

Run: `cd apps/web && node --test lib/page-surface/contracts.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/web/lib/api.ts apps/web/lib/page-surface/contracts.ts apps/web/lib/page-surface/contracts.test.ts apps/web/app/\(dashboard\)/onboarding/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/settings/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/scans/\[scan_id\]/page.tsx
git commit -m "refactor(web): normalize page-level API contracts"
```

---

### Task 3: Re-Architect the Findings Workspace

**Why first:** This is the highest ROI page in the product. It directly affects triage speed, remediation throughput, and export/reporting quality.

**Files:**
- Create: `apps/web/lib/findings/filter-state.ts`
- Create: `apps/web/lib/findings/filter-state.test.ts`
- Create: `apps/web/lib/findings/triage-policy.ts`
- Create: `apps/web/lib/findings/triage-policy.test.ts`
- Create: `apps/web/components/scanforge/findings-saved-view-bar.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/FindingDrawer.tsx`
- Modify: `apps/web/components/scanforge/findings-table.tsx`
- Modify: `apps/web/components/scanforge/filter-bar.tsx`

**Step 1: Write the failing filter-state test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { serializeFindingsFilters } from "./filter-state.ts";

test("serializes only active findings filters", () => {
  assert.deepEqual(
    serializeFindingsFilters({ severity: "critical", status: "", repositoryId: "r1" }),
    { severity: "critical", repositoryId: "r1" }
  );
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/findings/filter-state.test.ts`
Expected: FAIL because the helper does not exist yet.

**Step 3: Implement filter serialization and triage policy helpers**

Create helpers for:
- query-param sync
- saved-view payloads
- bulk-action availability by finding status
- repository/scanner label rendering

**Step 4: Split page responsibilities**

Refactor the route so it composes:
- filter state
- bulk action state
- drawer state
- pagination state

Keep the route thin and make `FindingDrawer` responsible only for detail interactions.

**Step 5: Add the highest-value enhancements**

Implement:
- saved views
- richer filter chips
- overdue/SLA badges
- repository full names instead of raw IDs
- explicit export-scope summary before export trigger

**Step 6: Run tests and build**

Run: `cd apps/web && node --test lib/findings/filter-state.test.ts lib/findings/triage-policy.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/web/lib/findings apps/web/components/scanforge/findings-saved-view-bar.tsx apps/web/components/scanforge/findings-table.tsx apps/web/components/scanforge/filter-bar.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/
git commit -m "feat(web): re-architect findings workspace for triage speed"
```

---

### Task 4: Re-Architect Organization Settings as a Governance Surface

**Why second:** The settings page governs GitHub connectivity, access control, and destructive actions. It is high leverage and high risk.

**Files:**
- Create: `apps/web/lib/governance/member-policy.ts`
- Create: `apps/web/lib/governance/member-policy.test.ts`
- Create: `apps/web/components/scanforge/member-invitations-panel.tsx`
- Create: `apps/web/components/scanforge/integration-status-card.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`

**Step 1: Write the failing member-policy test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { canRemoveMember } from "./member-policy.ts";

test("prevents removing the last owner", () => {
  assert.equal(canRemoveMember({ actorRole: "owner", targetRole: "owner", ownerCount: 1 }), false);
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/governance/member-policy.test.ts`
Expected: FAIL because the policy helper does not exist yet.

**Step 3: Implement governance policies**

Cover:
- member role changes
- last-owner protection
- invite-state rendering
- integration status messaging
- danger-zone guardrails

**Step 4: Break the page into explicit sections**

Move the page toward four composable panels:
- General settings
- Integrations
- Members and invitations
- Danger zone

**Step 5: Add the highest-value enhancements**

Implement:
- pending invite list and resend/cancel affordances
- role explanation text
- stronger delete confirmation UX
- integration health details for GitHub

**Step 6: Run tests and build**

Run: `cd apps/web && node --test lib/governance/member-policy.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/web/lib/governance apps/web/components/scanforge/member-invitations-panel.tsx apps/web/components/scanforge/integration-status-card.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/settings/page.tsx
git commit -m "feat(web): upgrade organization settings for governance workflows"
```

---

### Task 5: Re-Architect Onboarding for Activation

**Why third:** Onboarding determines time-to-first-scan. Current logic is useful but too local, too brittle, and not resumable enough.

**Files:**
- Create: `apps/web/lib/onboarding/next-step.ts`
- Create: `apps/web/lib/onboarding/next-step.test.ts`
- Create: `apps/web/components/scanforge/onboarding-next-actions.tsx`
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`
- Modify: `apps/web/app/(dashboard)/github/callback/page.tsx`

**Step 1: Write the failing next-step test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { deriveOnboardingNextActions } from "./next-step.ts";

test("recommends github connection immediately after org creation", () => {
  const actions = deriveOnboardingNextActions([
    { id: "create_org", completed: true },
    { id: "connect_github", completed: false },
  ]);

  assert.equal(actions[0]?.id, "connect_github");
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/onboarding/next-step.test.ts`
Expected: FAIL because the helper does not exist yet.

**Step 3: Implement onboarding next-action logic**

Support:
- role-aware next actions
- completion summaries
- resumable next-step cards
- persistent dismissal rules that can later move server-side

**Step 4: Refactor the onboarding route**

Separate:
- checklist fetch logic
- inline organization creation
- GitHub connection state
- completion next-actions

**Step 5: Improve callback resilience**

Update the GitHub callback page to render explicit recovery states when local install context is missing or the connect call fails.

**Step 6: Run tests and build**

Run: `cd apps/web && node --test lib/onboarding/next-step.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/web/lib/onboarding apps/web/components/scanforge/onboarding-next-actions.tsx apps/web/app/\(dashboard\)/onboarding/page.tsx apps/web/app/\(dashboard\)/github/callback/page.tsx
git commit -m "feat(web): rework onboarding for activation and recovery"
```

---

### Task 6: Re-Architect Scan Detail and Scan Operations

**Why fourth:** Operators need confidence and diagnostics when scans fail or stall. This improves supportability and trust in the platform.

**Files:**
- Create: `apps/web/lib/scans/lifecycle.ts`
- Create: `apps/web/lib/scans/lifecycle.test.ts`
- Create: `apps/web/components/scanforge/scan-timeline.tsx`
- Create: `apps/web/components/scanforge/scan-summary-cards.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx`

**Step 1: Write the failing lifecycle test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { deriveScanPhase } from "./lifecycle.ts";

test("maps running scans to active phase", () => {
  assert.equal(deriveScanPhase({ status: "running", scanner_runs: [] }), "active");
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/scans/lifecycle.test.ts`
Expected: FAIL because the helper does not exist yet.

**Step 3: Implement scan lifecycle helpers**

Cover:
- phase derivation
- action availability
- rerun payload derivation
- scan summary formatting
- artifact availability

**Step 4: Add a scan timeline and summary layer**

Refactor the detail page around timeline, summary, scanner runs, and failure diagnostics rather than raw sections.

**Step 5: Improve the scans list page**

Add:
- repository filter
- branch filter
- clearer action affordances for failed/stale scans
- scan-trigger presets

**Step 6: Run tests and build**

Run: `cd apps/web && node --test lib/scans/lifecycle.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/web/lib/scans apps/web/components/scanforge/scan-timeline.tsx apps/web/components/scanforge/scan-summary-cards.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/scans/
git commit -m "feat(web): improve scan lifecycle visibility and operations"
```

---

### Task 7: Re-Architect Suppressions for Governance Safety

**Why fifth:** Suppression workflows can quietly erode security posture if they stay simple CRUD. This page needs guardrails before scale.

**Files:**
- Create: `apps/web/lib/suppressions/rule-policy.ts`
- Create: `apps/web/lib/suppressions/rule-policy.test.ts`
- Create: `apps/web/components/scanforge/suppression-impact-preview.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/suppressions/page.tsx`

**Step 1: Write the failing rule-policy test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { describeSuppressionScope } from "./rule-policy.ts";

test("labels project scoped rules clearly", () => {
  assert.equal(describeSuppressionScope({ project_id: "p1" }), "project");
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/suppressions/rule-policy.test.ts`
Expected: FAIL because the helper does not exist yet.

**Step 3: Implement rule-policy helpers**

Support:
- rule scope labels
- expiration display
- approval requirement hints
- safe delete/toggle messaging

**Step 4: Refactor the page to support richer governance**

Prepare the page for:
- rule previews
- expiry metadata
- audit-friendly summaries
- organization vs project grouping

**Step 5: Run tests and build**

Run: `cd apps/web && node --test lib/suppressions/rule-policy.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/web/lib/suppressions apps/web/components/scanforge/suppression-impact-preview.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/suppressions/page.tsx
git commit -m "feat(web): harden suppression workflows for governance"
```

---

### Task 8: Upgrade Tier 2 Pages on Shared Infrastructure

**Why now:** These pages matter, but their ROI is lower than the five core workflows above. They should ride the new infrastructure instead of inventing more local patterns.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/[repo_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/exports/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/audit-logs/page.tsx`
- Modify: `apps/web/app/(dashboard)/notifications/page.tsx`
- Modify: `apps/web/app/(dashboard)/profile/page.tsx`

**Step 1: Write one failing test for a Tier 2 helper**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { summarizeNotificationGroups } from "../notifications/groups.ts";

test("groups unread finding notifications by type", () => {
  const groups = summarizeNotificationGroups([
    { id: "1", notification_type: "finding", is_read: false },
    { id: "2", notification_type: "finding", is_read: false },
  ]);

  assert.equal(groups[0]?.count, 2);
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/notifications/groups.test.ts`
Expected: FAIL because the helper does not exist yet.

**Step 3: Implement only shared helpers that unlock multiple pages**

Examples:
- repo health summary helpers
- scorecard comparison helpers
- notification grouping helpers
- export job status helpers

**Step 4: Refactor each Tier 2 page onto the new patterns**

Use:
- `page-state-panel`
- page contract helpers
- action policy helpers

**Step 5: Run tests and build**

Run: `cd apps/web && node --test lib/notifications/groups.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/web/lib apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/\[repo_id\]/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/scorecard/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/exports/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/audit-logs/page.tsx apps/web/app/\(dashboard\)/notifications/page.tsx apps/web/app/\(dashboard\)/profile/page.tsx
git commit -m "feat(web): migrate tier-2 pages onto shared page architecture"
```

---

### Task 9: Clean Up Tier 3 Pages and Route Entry Points

**Why last:** These pages are important but they do not move the same operational metrics as the main workflow pages.

**Files:**
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/app/auth/[path]/page.tsx`
- Modify: `apps/web/app/account/[path]/page.tsx`

**Step 1: Write the failing route-entry test**

```ts
import test from "node:test";
import assert from "node:assert/strict";

import { resolveHomeRoute } from "./route-entry.ts";

test("sends signed-out users to sign-in", () => {
  assert.equal(resolveHomeRoute({ hasSession: false }), "/auth/sign-in");
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && node --test lib/page-surface/route-entry.test.ts`
Expected: FAIL because the helper does not exist yet.

**Step 3: Implement route-entry logic**

Add helpers for:
- home redirect resolution
- auth shell copy selection
- account shell section titles

**Step 4: Apply the route-entry cleanup**

Update the root route and auth/account shells to use the shared route-entry logic and clearer user guidance.

**Step 5: Run tests and build**

Run: `cd apps/web && node --test lib/page-surface/route-entry.test.ts`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/web/lib/page-surface/route-entry.ts apps/web/lib/page-surface/route-entry.test.ts apps/web/app/page.tsx apps/web/app/auth/\[path\]/page.tsx apps/web/app/account/\[path\]/page.tsx
git commit -m "feat(web): clean up route entry points and auth shells"
```

---

## Highest ROI First

If scope must be cut, deliver in this exact order:

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7

Only after those are complete should Task 8 and Task 9 begin.

---

## Success Criteria

- Findings triage becomes the fastest page in the app for power users.
- Governance-sensitive pages stop relying on ad hoc destructive-action patterns.
- Onboarding becomes resumable, explicit, and resilient to callback failures.
- Scan operations expose enough state to explain failure and rerun behavior.
- Suppressions gain governance guardrails before broader adoption.
- Tier 2 pages reuse the new architecture instead of growing more route-local complexity.

---

## Verification Checklist

- `cd apps/web && node --test lib/**/*.test.ts`
- `cd apps/web && npm run build`
- Manual verification of:
  - findings filter/save/export flow
  - org settings member and GitHub flows
  - onboarding create-org and GitHub callback flow
  - scan trigger, failure, rerun, and delete flow
  - suppression create/toggle/delete flow

Plan complete and saved to `docs/plans/2026-03-31-page-audit-architecture-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
