# ScanForge Full UI Rollout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Roll out the new ScanForge editorial-industrial UI/UX system across every existing page in `apps/web` so the entire product feels cohesive, intentional, and production-ready.

**Architecture:** Implement the redesign from the inside out. First establish shared tokens, shell layout, navigation, page framing, and common product surfaces. Then migrate public/auth pages, org-level views, project-level views, and detail workflows onto those shared patterns. Avoid one-off page styling; every screen should be composed from the same design primitives and route-specific content blocks.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4, Radix UI primitives, Framer Motion, Recharts, existing ScanForge `components/ui` and `components/scanforge`.

## Route Inventory

This rollout must cover every current route file:

- `apps/web/app/page.tsx`
- `apps/web/app/layout.tsx`
- `apps/web/app/auth/[path]/page.tsx`
- `apps/web/app/account/[path]/page.tsx`
- `apps/web/app/(dashboard)/layout.tsx`
- `apps/web/app/(dashboard)/dashboard/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/audit-logs/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/[repo_id]/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/exports/page.tsx`
- `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/suppressions/page.tsx`
- `apps/web/app/(dashboard)/notifications/page.tsx`
- `apps/web/app/(dashboard)/onboarding/page.tsx`
- `apps/web/app/(dashboard)/profile/page.tsx`
- `apps/web/app/(dashboard)/github/callback/page.tsx`

## Design System Rules For This Rollout

- All pages must inherit the same tokenized background, surface, border, typography, and motion system from `globals.css`.
- All dashboard pages must use the same app shell, left navigation logic, page header rhythm, content width rules, and top utility bar behavior.
- All dense operational pages must prefer reusable product components over page-local styling.
- Status, severity, validation, loading, and empty states must be represented consistently across pages.
- Public/auth/onboarding screens can be more spacious, but they must still feel like the same product.

## Task 1: Lock the Token Layer and Visual Foundation

**Files:**
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/app/layout.tsx`
- Modify: `apps/web/components/providers/theme-provider.tsx`
- Inspect: `apps/web/components/ui/button.tsx`
- Inspect: `apps/web/components/ui/card.tsx`
- Inspect: `apps/web/components/ui/input.tsx`
- Inspect: `apps/web/components/ui/table.tsx`

**Step 1: Review global tokens and current typography usage**

Run:

```bash
rg -n "primary|surface|background|text-|font-display|font-sans" apps/web/app apps/web/components
```

Expected: Existing token and utility usage appears in `globals.css` and shared components.

**Step 2: Write the updated global token map**

Implement:
- editorial-industrial color variables
- type scale variables
- spacing and radius variables
- motion duration/easing tokens
- unified focus ring token
- reusable utility classes for panel, section label, content frame, and subdued metadata

**Step 3: Update root layout to support the new brand framing**

Implement:
- app-level background treatment
- consistent metadata/viewport setup if needed
- font loading and root body classes aligned to the new type system

**Step 4: Verify the token layer compiles**

Run:

```bash
cd apps/web && npm run build
```

Expected: Build passes with the new token layer before route work begins.

**Step 5: Commit**

```bash
git add apps/web/app/globals.css apps/web/app/layout.tsx apps/web/components/providers/theme-provider.tsx
git commit -m "feat: establish scanforge visual foundation"
```

## Task 2: Rebuild the Shared App Shell and Navigation System

**Files:**
- Modify: `apps/web/app/(dashboard)/layout.tsx`
- Modify: `apps/web/components/scanforge/logo.tsx`
- Create: `apps/web/components/scanforge/app-shell.tsx`
- Create: `apps/web/components/scanforge/sidebar-nav.tsx`
- Create: `apps/web/components/scanforge/top-bar.tsx`
- Create: `apps/web/components/scanforge/section-frame.tsx`
- Modify: `apps/web/components/scanforge/breadcrumb.tsx`
- Modify: `apps/web/components/scanforge/command-palette.tsx`
- Modify: `apps/web/components/scanforge/keyboard-shortcuts-modal.tsx`

**Step 1: Extract the current dashboard shell into reusable shell components**

Implement:
- fixed left rail
- top utility bar
- content container
- mobile sheet navigation
- route-aware nav grouping

**Step 2: Replace decorative legacy styling in the shell**

Implement:
- remove purple/gradient-heavy active states
- introduce stronger structure through borders, spacing, typography, and restrained color
- unify active, hover, focus, and collapsed states

**Step 3: Standardize shell affordances**

Implement:
- command palette entry point
- notifications entry point
- org/project context visibility
- consistent page transition wrapper

**Step 4: Verify shell behavior**

Run:

```bash
cd apps/web && npm run build
```

Expected: The dashboard shell renders for all authenticated pages without route regressions.

**Step 5: Commit**

```bash
git add apps/web/app/'(dashboard)'/layout.tsx apps/web/components/scanforge
git commit -m "feat: rebuild scanforge app shell and navigation"
```

## Task 3: Standardize Product-Level Shared Components

**Files:**
- Modify: `apps/web/components/scanforge/page-header.tsx`
- Modify: `apps/web/components/scanforge/empty-state.tsx`
- Modify: `apps/web/components/scanforge/loading-skeleton.tsx`
- Modify: `apps/web/components/scanforge/enhanced-card.tsx`
- Modify: `apps/web/components/scanforge/enhanced-forms.tsx`
- Modify: `apps/web/components/scanforge/filter-bar.tsx`
- Modify: `apps/web/components/scanforge/status-badge.tsx`
- Modify: `apps/web/components/scanforge/severity-badge.tsx`
- Modify: `apps/web/components/scanforge/stat-card.tsx`
- Modify: `apps/web/components/scanforge/scorecard-ring.tsx`
- Modify: `apps/web/components/scanforge/risk-score-gauge.tsx`
- Modify: `apps/web/components/scanforge/severity-breakdown.tsx`
- Modify: `apps/web/components/scanforge/trend-chart.tsx`
- Modify: `apps/web/components/scanforge/findings-bar-chart.tsx`

**Step 1: Refactor page framing primitives**

Implement:
- shared eyebrow/title/description/action layout
- section heading treatment
- reusable content sections and panel headers

**Step 2: Refactor states**

Implement:
- empty state family
- loading skeleton family
- error/zero-data panel style

**Step 3: Refactor data-display components**

Implement:
- stat cards
- status badges
- severity badges
- score and trend components
- filter utility row

**Step 4: Verify no page-local duplicate styling remains for core patterns**

Run:

```bash
rg -n "rounded-xl border border-|bg-surface|text-text-tertiary uppercase" 'apps/web/app/(dashboard)'
```

Expected: Repetition decreases as shared product components absorb common patterns.

**Step 5: Commit**

```bash
git add apps/web/components/scanforge
git commit -m "feat: standardize scanforge product components"
```

## Task 4: Redesign the Public Entry and Auth Surfaces

**Files:**
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/app/auth/[path]/page.tsx`
- Modify: `apps/web/app/account/[path]/page.tsx`
- Modify: `apps/web/app/(dashboard)/github/callback/page.tsx`
- Create: `apps/web/components/scanforge/public-hero.tsx`
- Create: `apps/web/components/scanforge/auth-shell.tsx`

**Step 1: Replace the root redirect with an intentional landing decision**

Implement one of:
- a real landing page with CTA to sign in/onboard
- or a role-aware redirect page with branded transition UI

Recommendation: build a minimal but real landing page.

**Step 2: Redesign auth and account pages**

Implement:
- split or centered auth shell
- brand framing
- clearer copy hierarchy
- consistent form styles and support messaging

**Step 3: Redesign GitHub callback/loading states**

Implement:
- progress messaging
- success/failure states
- graceful handoff back into onboarding or dashboard

**Step 4: Verify public/auth routing**

Run:

```bash
cd apps/web && npm run build
```

Expected: Public and auth routes compile and preserve auth flow behavior.

**Step 5: Commit**

```bash
git add apps/web/app/page.tsx apps/web/app/auth apps/web/app/account apps/web/app/'(dashboard)'/github/callback apps/web/components/scanforge/public-hero.tsx apps/web/components/scanforge/auth-shell.tsx
git commit -m "feat: redesign public and auth surfaces"
```

## Task 5: Redesign Org-Level Overview, Settings, and Oversight Pages

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/audit-logs/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`
- Modify: `apps/web/app/(dashboard)/notifications/page.tsx`
- Modify: `apps/web/app/(dashboard)/profile/page.tsx`
- Create: `apps/web/components/scanforge/overview-metric-panel.tsx`
- Create: `apps/web/components/scanforge/activity-feed.tsx`
- Create: `apps/web/components/scanforge/settings-section.tsx`

**Step 1: Redesign dashboard index and organization overview**

Implement:
- a consistent org selection / org overview rhythm
- summary metrics
- current risk and activity context
- stronger empty states when users have no orgs/projects yet

**Step 2: Redesign scorecard and audit surfaces**

Implement:
- scorecard as an executive/operational report surface
- audit log as a dense but legible event stream

**Step 3: Redesign settings, notifications, and profile**

Implement:
- sectioned settings layout
- clear account preferences and security framing
- notifications with meaningful grouping and read-state treatment

**Step 4: Verify org-level consistency**

Run:

```bash
cd apps/web && npm run build
```

Expected: Org-level pages all inherit the same shell, header, section, and panel language.

**Step 5: Commit**

```bash
git add apps/web/app/'(dashboard)'/dashboard/page.tsx apps/web/app/'(dashboard)'/dashboard/'[org_id]' apps/web/app/'(dashboard)'/notifications/page.tsx apps/web/app/'(dashboard)'/profile/page.tsx apps/web/components/scanforge
git commit -m "feat: redesign org-level overview and governance pages"
```

## Task 6: Redesign Onboarding End-to-End

**Files:**
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`
- Modify: `apps/web/components/scanforge/onboarding-step.tsx`
- Modify: `apps/web/components/scanforge/stepper.tsx`
- Modify: `apps/web/components/scanforge/enhanced-forms.tsx`
- Create: `apps/web/components/scanforge/onboarding-shell.tsx`
- Create: `apps/web/components/scanforge/onboarding-summary-panel.tsx`

**Step 1: Reframe onboarding as a guided control flow**

Implement:
- clear step sequence
- progress language
- what-happens-next messaging
- fewer generic form stacks

**Step 2: Improve connection and setup feedback**

Implement:
- integration state panels
- scan readiness summary
- success/failure recovery guidance

**Step 3: Verify onboarding clarity**

Manual QA:
- new user with no orgs
- user with org but no project
- user with project but no connected repo

**Step 4: Commit**

```bash
git add apps/web/app/'(dashboard)'/onboarding/page.tsx apps/web/components/scanforge/onboarding-step.tsx apps/web/components/scanforge/stepper.tsx apps/web/components/scanforge/enhanced-forms.tsx apps/web/components/scanforge/onboarding-shell.tsx apps/web/components/scanforge/onboarding-summary-panel.tsx
git commit -m "feat: redesign scanforge onboarding flow"
```

## Task 7: Redesign Project Overview and Repository Surfaces

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/[repo_id]/page.tsx`
- Modify: `apps/web/components/scanforge/repo-health-card.tsx`
- Modify: `apps/web/components/scanforge/schedule-indicator.tsx`
- Create: `apps/web/components/scanforge/repository-hero.tsx`
- Create: `apps/web/components/scanforge/repository-meta-panel.tsx`

**Step 1: Redesign the project overview page as the core control-room surface**

Implement:
- stronger header and project context
- risk summary band
- trend and activity structure
- top findings and repo health layout using reusable panels

**Step 2: Redesign repositories index**

Implement:
- utility bar with search/actions
- repository cards or compact rows that fit the new visual system
- eliminate emoji/icon shortcuts that break visual coherence

**Step 3: Redesign repository detail**

Implement:
- repository identity header
- scan readiness/coverage panels
- findings summary, latest scan, schedule, and actions

**Step 4: Verify repository workflows**

Manual QA:
- project with zero repos
- project with one repo
- project with multiple repos and partial stats

**Step 5: Commit**

```bash
git add apps/web/app/'(dashboard)'/dashboard/'[org_id]'/projects/'[project_id]'/page.tsx apps/web/app/'(dashboard)'/dashboard/'[org_id]'/projects/'[project_id]'/repositories apps/web/components/scanforge/repo-health-card.tsx apps/web/components/scanforge/schedule-indicator.tsx apps/web/components/scanforge/repository-hero.tsx apps/web/components/scanforge/repository-meta-panel.tsx
git commit -m "feat: redesign project overview and repository surfaces"
```

## Task 8: Redesign Findings Inventory and Finding Detail

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/FindingDrawer.tsx`
- Modify: `apps/web/components/scanforge/findings-table.tsx`
- Modify: `apps/web/components/scanforge/finding-drawer.tsx`
- Modify: `apps/web/components/scanforge/filter-bar.tsx`
- Create: `apps/web/components/scanforge/findings-toolbar.tsx`
- Create: `apps/web/components/scanforge/finding-history-panel.tsx`

**Step 1: Rebuild findings inventory around speed and clarity**

Implement:
- unified filter/search/action bar
- stronger table hierarchy
- consistent pagination
- batch action affordances that do not clutter the default view

**Step 2: Rebuild finding detail presentation**

Implement:
- issue summary
- evidence/context sections
- references and audit history
- suppression/resolve/reopen actions framed with clear consequences

**Step 3: Reduce page-local inline UI helpers**

Move:
- filter pills
- pagination treatment
- toolbar actions
into shared product components where practical

**Step 4: Verify triage usability**

Manual QA:
- keyboard-only table navigation
- drawer open/close and focus restoration
- filter persistence in URL

**Step 5: Commit**

```bash
git add apps/web/app/'(dashboard)'/dashboard/'[org_id]'/projects/'[project_id]'/findings apps/web/components/scanforge/findings-table.tsx apps/web/components/scanforge/finding-drawer.tsx apps/web/components/scanforge/findings-toolbar.tsx apps/web/components/scanforge/finding-history-panel.tsx
git commit -m "feat: redesign findings inventory and detail workflow"
```

## Task 9: Redesign Scans, Exports, and Suppressions

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/exports/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/suppressions/page.tsx`
- Create: `apps/web/components/scanforge/scan-timeline.tsx`
- Create: `apps/web/components/scanforge/export-history-table.tsx`
- Create: `apps/web/components/scanforge/suppression-list.tsx`

**Step 1: Redesign scans index**

Implement:
- denser operational list
- stronger execution-state cues
- quick access to recent failures, queued runs, and completed reports

**Step 2: Redesign scan detail**

Implement:
- execution timeline
- per-scanner breakdown
- artifact/log state panels
- resulting findings summary

**Step 3: Redesign exports and suppressions**

Implement:
- report/document treatment for exports
- governance-focused list and detail patterns for suppressions

**Step 4: Verify operations workflows**

Manual QA:
- scan with no artifacts
- failed scan
- completed scan
- empty export history
- suppressions list with and without data

**Step 5: Commit**

```bash
git add apps/web/app/'(dashboard)'/dashboard/'[org_id]'/projects/'[project_id]'/scans apps/web/app/'(dashboard)'/dashboard/'[org_id]'/projects/'[project_id]'/exports/page.tsx apps/web/app/'(dashboard)'/dashboard/'[org_id]'/projects/'[project_id]'/suppressions/page.tsx apps/web/components/scanforge/scan-timeline.tsx apps/web/components/scanforge/export-history-table.tsx apps/web/components/scanforge/suppression-list.tsx
git commit -m "feat: redesign scan, export, and suppression surfaces"
```

## Task 10: Responsive, Accessibility, and State Completion Pass

**Files:**
- Modify: `apps/web/components/scanforge/mobile-responsive.tsx`
- Modify: all touched route files and shared components as needed

**Step 1: Audit breakpoints**

Manual QA:
- 1440px desktop
- 1024px laptop
- 768px tablet
- 390px mobile

Confirm:
- no clipped controls
- no table overflow without deliberate handling
- mobile nav and drawers remain usable

**Step 2: Audit accessibility**

Check:
- focus visibility
- semantic heading order
- explicit labels
- button names
- color contrast
- color-independent status signaling

**Step 3: Audit state completeness**

Check:
- loading
- empty
- error
- partial data
- success confirmation

**Step 4: Commit**

```bash
git add apps/web
git commit -m "fix: complete responsive and accessibility pass for ui rollout"
```

## Task 11: Final Verification and Cleanup

**Files:**
- Modify: `apps/web/README.md` if design-system usage needs documentation
- Modify: `docs/plans/2026-03-30-scanforge-full-ui-rollout-plan.md` only if execution notes are needed

**Step 1: Run final verification**

Run:

```bash
cd apps/web && npm run build
```

Expected: PASS

If lint is configured and working:

```bash
cd apps/web && npm run lint
```

Expected: PASS

**Step 2: Perform route smoke test**

Manually verify every current route listed in the Route Inventory using seeded or available app data.

**Step 3: Document any known gaps**

If any routes are intentionally deferred, record them explicitly. The target state for this plan is zero deferred pages.

**Step 4: Commit**

```bash
git add apps/web README.md docs/plans/2026-03-30-scanforge-full-ui-rollout-plan.md
git commit -m "docs: finalize full scanforge ui rollout plan"
```

## Definition of Done

The redesign is complete only when all of the following are true:

- Every route in the Route Inventory reflects the new UI/UX direction.
- Shared tokens and product primitives drive the majority of page presentation.
- No legacy purple-gradient or generic AI-dashboard styling remains in primary product surfaces.
- Public, auth, onboarding, dashboard, findings, scans, exports, suppressions, settings, notifications, and profile views feel like one product.
- Responsive behavior is deliberate, not incidental.
- Focus, keyboard navigation, empty states, loading states, and error states are consistent.
- `npm run build` passes in `apps/web`.

## Execution Order Recommendation

Use this order during implementation:

1. Foundation
2. Shell
3. Shared product primitives
4. Public/auth
5. Org-level pages
6. Onboarding
7. Project/repository pages
8. Findings
9. Scans/exports/suppressions
10. Accessibility/responsive pass
11. Final verification

This order ensures every later page migration inherits the new system rather than re-solving layout and styling at the route level.
