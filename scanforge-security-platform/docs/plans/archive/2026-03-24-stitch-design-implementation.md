# Stitch Design Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the 4 Stitch MCP screen designs across ScanForge pages with live API data and recharts visualizations.

**Architecture:** Install recharts for bar charts. Create 3 new shared components (RiskScoreGauge, FindingsBarChart, SeverityBreakdown). Update 4 pages: Project Overview → "Security Overview Dashboard", Findings → "Security Findings Inventory", Repositories → "Connected Repositories Workspace", Organizations → "Organizations" card layout. All components consume live API data from existing endpoints.

**Tech Stack:** React, Next.js App Router, TypeScript, Tailwind CSS v4, recharts, lucide-react, existing ScanForge API client

---

## Stitch Design Reference

**Theme (already implemented in globals.css):**
- Dark mode, `#090b10` background, `#0f1118` surface
- Primary: `#135bec`, Secondary: `#8b5cf6`
- Font: Space Grotesk (display/sans), JetBrains Mono (mono)
- Roundness: 8px default, 12px large
- Severity: Critical=red `#ef4444`, High=orange `#f97316`, Medium=yellow `#eab308`, Low=green `#22c55e`

**Design Screens:**
1. **Security Overview Dashboard** — 3 stat cards (Total Vulns w/ severity dots, Risk Score gauge, High Priority Findings w/ CVE list), bar chart (Findings Over 30 Days), Recent Activity feed
2. **Security Findings Inventory** — Search + rounded filter pills, "Download Report" button, data table (Finding Name, Severity badge, Repository, Status, Detected On, Actions), numbered pagination
3. **Connected Repositories Workspace** — Search + "Connect Repository" button, 2×2 card grid (tech icon, repo name, last scan time, letter grade badge)
4. **Organizations** — Search + "New Organization" button, cards with lock icon and action buttons

---

### Task 1: Install recharts

**Files:**
- Modify: `apps/web/package.json`

**Step 1: Install recharts**

```bash
cd apps/web && npm install recharts
```

**Step 2: Verify installation**

```bash
cd apps/web && node -e "require('recharts'); console.log('OK')"
```

**Step 3: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "chore: install recharts for dashboard visualizations"
```

---

### Task 2: Create RiskScoreGauge Component

**Files:**
- Create: `apps/web/components/scanforge/risk-score-gauge.tsx`

**Step 1: Create the gauge component**

A semicircular gauge (like a speedometer) that shows score 0-100 with a colored arc and "Moderate"/"Good"/"Critical" label underneath. Matches the Stitch design: large number in center, arc colored by score, label text below.

```tsx
import { cn } from "@/lib/utils";

interface RiskScoreGaugeProps {
  score: number; // 0-100
  className?: string;
}

function getScoreLabel(score: number) {
  if (score >= 80) return { label: "Good", color: "text-success" };
  if (score >= 60) return { label: "Moderate", color: "text-warning" };
  if (score >= 40) return { label: "At Risk", color: "text-severity-high" };
  return { label: "Critical", color: "text-danger" };
}

function getArcColor(score: number) {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}

export function RiskScoreGauge({ score, className }: RiskScoreGaugeProps) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const { label, color } = getScoreLabel(clampedScore);
  const arcColor = getArcColor(clampedScore);

  // Semicircle SVG gauge
  const radius = 52;
  const strokeWidth = 8;
  const cx = 60;
  const cy = 60;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference - (clampedScore / 100) * circumference;

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div className="relative">
        <svg width="120" height="72" viewBox="0 0 120 72">
          {/* Background arc */}
          <path
            d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
            fill="none"
            stroke="var(--color-border-strong)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Score arc */}
          <path
            d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
            fill="none"
            stroke={arcColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        {/* Score number */}
        <div className="absolute inset-0 flex items-end justify-center pb-1">
          <span className="text-3xl font-bold font-display tracking-tight text-text-primary">
            {clampedScore}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-[10px] text-text-tertiary font-mono">out of 100</span>
      </div>
      <span className={cn(
        "mt-1 inline-flex items-center rounded-full px-3 py-0.5 text-xs font-semibold",
        color === "text-success" && "bg-success/10 text-success",
        color === "text-warning" && "bg-warning/10 text-warning",
        color === "text-severity-high" && "bg-severity-high/10 text-severity-high",
        color === "text-danger" && "bg-danger/10 text-danger",
      )}>
        {label}
      </span>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add apps/web/components/scanforge/risk-score-gauge.tsx
git commit -m "feat: add RiskScoreGauge component for dashboard"
```

---

### Task 3: Create FindingsBarChart Component

**Files:**
- Create: `apps/web/components/scanforge/findings-bar-chart.tsx`

**Step 1: Create the recharts bar chart**

Stacked bar chart showing findings over 30 days. Purple bars for low/medium, yellow/orange for high/critical. Matches the Stitch design with vertical bars and date x-axis.

```tsx
"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { cn } from "@/lib/utils";

interface FindingsBarChartProps {
  data: Array<{
    date: string;
    count?: number;
    critical?: number;
    high?: number;
    medium?: number;
    low?: number;
    info?: number;
  }>;
  className?: string;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-surface-elevated px-3 py-2 shadow-lg">
      <p className="text-xs text-text-tertiary font-mono mb-1">{label}</p>
      {payload.map((entry: any) => (
        <p key={entry.name} className="text-xs font-medium" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

export function FindingsBarChart({ data, className }: FindingsBarChartProps) {
  if (!data || data.length === 0) return null;

  // If data only has count field, use it directly; otherwise use severity breakdown
  const hasSeverityBreakdown = data.some(d => d.critical !== undefined || d.high !== undefined);

  const chartData = data.map((d) => ({
    date: d.date.slice(5), // "MM-DD" format
    ...(hasSeverityBreakdown
      ? { critical: d.critical ?? 0, high: d.high ?? 0, medium: d.medium ?? 0, low: d.low ?? 0, info: d.info ?? 0 }
      : { findings: d.count ?? 0 }),
  }));

  return (
    <div className={cn("rounded-xl border border-border bg-surface p-5", className)}>
      <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-4">
        Findings Over Last 30 Days
      </h3>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} barCategoryGap="20%">
          <CartesianGrid
            vertical={false}
            stroke="var(--color-border)"
            strokeDasharray="4 4"
          />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--color-text-tertiary)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "var(--color-text-tertiary)", fontSize: 10, fontFamily: "var(--font-mono)" }}
            axisLine={false}
            tickLine={false}
            width={30}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "var(--color-surface-hover)" }} />
          {hasSeverityBreakdown ? (
            <>
              <Bar dataKey="critical" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
              <Bar dataKey="high" stackId="a" fill="#f97316" radius={[0, 0, 0, 0]} />
              <Bar dataKey="medium" stackId="a" fill="#eab308" radius={[0, 0, 0, 0]} />
              <Bar dataKey="low" stackId="a" fill="#8b5cf6" radius={[0, 0, 0, 0]} />
              <Bar dataKey="info" stackId="a" fill="#135bec" radius={[2, 2, 0, 0]} />
            </>
          ) : (
            <Bar dataKey="findings" fill="#8b5cf6" radius={[3, 3, 0, 0]} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add apps/web/components/scanforge/findings-bar-chart.tsx
git commit -m "feat: add FindingsBarChart recharts component"
```

---

### Task 4: Create SeverityBreakdown Component

**Files:**
- Create: `apps/web/components/scanforge/severity-breakdown.tsx`

**Step 1: Create the severity dots component**

Shows colored dots with severity counts in a compact row. Matches the Stitch design showing "● Crit: 52  ● High: 45  ● Med: 63  ● Low: 25" next to the total count.

```tsx
import { cn } from "@/lib/utils";

interface SeverityBreakdownProps {
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
  info?: number;
  className?: string;
}

const ITEMS = [
  { key: "critical", label: "Crit", dot: "bg-severity-critical", text: "text-severity-critical" },
  { key: "high", label: "High", dot: "bg-severity-high", text: "text-severity-high" },
  { key: "medium", label: "Med", dot: "bg-severity-medium", text: "text-severity-medium" },
  { key: "low", label: "Low", dot: "bg-severity-low", text: "text-severity-low" },
] as const;

export function SeverityBreakdown({ critical = 0, high = 0, medium = 0, low = 0, className }: SeverityBreakdownProps) {
  const counts: Record<string, number> = { critical, high, medium, low };

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {ITEMS.map((item) => (
        <div key={item.key} className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", item.dot)} />
          <span className="text-xs text-text-tertiary w-8">{item.label}:</span>
          <span className={cn("text-xs font-bold font-mono", item.text)}>
            {counts[item.key]}
          </span>
        </div>
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add apps/web/components/scanforge/severity-breakdown.tsx
git commit -m "feat: add SeverityBreakdown dot component"
```

---

### Task 5: Update Project Overview → Security Overview Dashboard

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`

**Step 1: Rewrite the project overview page**

Replace the current layout with the Stitch "Security Overview Dashboard" design:
- Top: Page title "Security Overview Dashboard"
- Row 1: 3 cards — Total Vulnerabilities (large number + severity breakdown dots), Risk Score (gauge), High Priority Findings (count + top CVE alerts)
- Row 2: FindingsBarChart (left), Recent Activity (right)
- Use existing API calls: `findings.stats()`, `scorecard.get()`, `findings.trend()`, `auditLogs.listProject()`

The page should keep all existing data fetching and add the new layout. Import the new components: `RiskScoreGauge`, `FindingsBarChart`, `SeverityBreakdown`.

Key layout structure:
```
┌──────────────────────────────────────────────────────────────┐
│ Security Overview Dashboard                                    │
├──────────────────┬──────────────────┬────────────────────────┤
│ Total Vulns: 145 │ Risk Score: 72   │ High Priority: 12      │
│ ● Crit: 52       │ [gauge graphic]  │ Top Alerts:            │
│ ● High: 45       │ "Moderate"       │ CVE-2024-1234 ...      │
│ ● Med: 63        │                  │ CVE-2024-1235 ...      │
│ ● Low: 25        │                  │                        │
│ Trend ↗ 12 month │                  │                        │
├──────────────────────────────────┬───────────────────────────┤
│ Findings Over Last 30 Days      │ Recent Activity           │
│ [bar chart]                     │ ● New scan completed...   │
│                                 │ ● High severity vuln...   │
│                                 │ ● User changed permi...   │
└─────────────────────────────────┴───────────────────────────┘
```

Replace the full page component. Preserve existing data fetching logic but restructure the JSX to match the Stitch layout above. Keep all API calls: `api.projects.get()`, `api.findings.stats()`, `api.scans.list()`, `api.scorecard.get()`, `api.findings.trend()`, `api.repositories.list()`, `api.auditLogs.listProject()`.

**Step 2: Verify it builds**

```bash
cd apps/web && npx next build --no-lint 2>&1 | tail -20
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/page.tsx
git commit -m "feat: redesign project overview to match Stitch Security Overview Dashboard"
```

---

### Task 6: Update Findings Page → Security Findings Inventory

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`

**Step 1: Update the findings page**

Changes to match Stitch "Security Findings Inventory" design:
1. **Page title:** "Security Findings Inventory" with subtitle "Manage your team's security issues and vulnerabilities across repositories."
2. **Filter pills:** Convert existing FilterBar selects to rounded pill buttons that show label + "(All)" or selected value. Layout: `[Search] [Severity (All)] [Status (Open)] [Repository (All)] [Assignee (All)]` — then `[Download Report]` button on right.
3. **Table columns:** Reorder to: Finding Name, Severity, Repository, Status, Detected On, Actions (3-dot menu). Remove Category, Age columns.
4. **Severity badges:** Make them filled pill badges — CRITICAL (red bg), HIGH (orange bg), MEDIUM (yellow bg), LOW (green/teal bg) — uppercase text.
5. **Pagination:** Replace Previous/Next with numbered page buttons: `< 1 2 3 ... 5 >` with active page highlighted in primary color.
6. **Download Report button:** Purple primary button in header area.

Update the PageHeader, FilterBar usage, FindingsTable, and pagination section. Keep all existing filter/sort/bulk logic intact.

**Step 2: Verify it builds**

```bash
cd apps/web && npx next build --no-lint 2>&1 | tail -20
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/page.tsx
git commit -m "feat: redesign findings page to match Stitch Security Findings Inventory"
```

---

### Task 7: Update Repositories Page → Connected Repositories Workspace

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`

**Step 1: Update the repositories page**

Changes to match Stitch "Connected Repositories Workspace" design:
1. **Title:** "Connected Repositories Workspace" with subtitle "Continuous code repository monitoring and vulnerability management."
2. **Card grid:** 2×2 grid (`grid-cols-2`) instead of 3-col. Each card has:
   - Left: Tech language icon (use a colored icon based on repo name heuristics — Python/Go/JS/TS logos or fallback to Database icon)
   - Center: Repo name + "Last scan: X hours ago" subtitle
   - Right: Letter grade badge (A+/B/C/D/F) — colored circle badge
3. **"Connect Repository" button:** Purple primary button in top right
4. **Search bar:** Simple search input above the grid
5. Remove the "Schedules" expand button from each card (move to repo detail page only)

Grade derivation: Use existing `findingStats` — calculate score as `100 - (critical×25 + open×3)`, then map to letter grade.

**Step 2: Verify it builds**

```bash
cd apps/web && npx next build --no-lint 2>&1 | tail -20
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/page.tsx
git commit -m "feat: redesign repositories page to match Stitch Connected Repositories Workspace"
```

---

### Task 8: Update Organizations Page

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/page.tsx`

**Step 1: Update the organizations page**

Changes to match Stitch "Organizations" design:
1. **Title:** "Organizations" with subtitle "Manage your teams and workspaces"  ← already correct
2. **"New Organization" button:** Purple primary button  ← already correct
3. **Card layout:** Change from row-style links to wider cards:
   - Lock/shield icon on left (colored)
   - Org name in center
   - Grade badge (A+/B/C) and settings gear icon on right
4. **Search bar:** Already exists ← keep
5. Cards should be single-column or 2-col max with more padding, matching the Stitch screenshot where the card is wider and less dense.

**Step 2: Verify it builds**

```bash
cd apps/web && npx next build --no-lint 2>&1 | tail -20
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/page.tsx
git commit -m "feat: redesign organizations page to match Stitch design"
```

---

### Task 9: Final Polish & Build Verification

**Step 1: Full build check**

```bash
cd apps/web && npx next build --no-lint
```

**Step 2: Fix any build errors**

Address any TypeScript or import errors.

**Step 3: Final commit**

```bash
git add -A
git commit -m "fix: resolve build issues from Stitch design implementation"
```
