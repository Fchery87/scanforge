# ScanForge UI/UX Overhaul — Implementation Plan

> **Scope**: Complete frontend redesign — new design system, component library, typography, color system, animations, responsive layout, and page-by-page rebuild.
> **Stack**: Next.js 16, React 19, Tailwind CSS v4, shadcn/ui, Framer Motion
> **Timeline**: 5 phases, ~65 files changed/created

---

## Aesthetic Direction

**"Cyber-Industrial Precision"** — a security platform that feels like a command center. Sharp, geometric, with controlled luminosity. Bloomberg Terminal's information density meets modern SaaS polish.

### Typography

| Role | Font | Weight | Why |
|------|------|--------|-----|
| Display / Headlines | **Syne** | 600–800 | Geometric, angular, feels like precision engineering. Distinctive without being illegible. |
| Body / UI | **Plus Jakarta Sans** | 400–600 | Excellent readability, friendly but professional. More character than Inter. |
| Data / Code / Mono | **JetBrains Mono** | 400–500 | The security audience will recognize and trust it. Perfect ligatures for code/data. |

All three available on Google Fonts. Loaded via `next/font/google` for zero-layout-shift.

### Color System

#### Core Palette (HSL-based for Tailwind)

```
--background:       220 25% 5%        #080B14  — near-black base
--surface:          220 20% 9%        #121826  — cards, panels
--surface-hover:    220 18% 12%       #1A2035  — interactive lift
--surface-elevated: 220 16% 15%       #212A3E  — modals, dropdowns
--border:           220 15% 18%       #2A3347  — subtle borders
--border-strong:    220 14% 24%       #384459  — defined borders

--text-primary:     210 20% 92%       #E2E8F0  — warm white
--text-secondary:   215 14% 58%       #8B949E  — muted
--text-tertiary:    215 12% 38%       #545D6E  — subtle hints

--primary:          217 91% 60%       #3B82F6  — electric blue
--primary-glow:     217 91% 60% / 15%         — blue glow halo
--secondary:        263 70% 58%       #8B5CF6  — violet accent
--accent:           199 89% 48%       #0EA5E9  — cyan highlight

--success:          160 84% 39%       #10B981  — emerald
--warning:          38 92% 50%        #F59E0B  — amber
--danger:           0 84% 60%         #EF4444  — rose
--info:             189 94% 43%       #06B6D4  — cyan
```

#### Glow System
Every interactive element gets a subtle luminous halo:
- Primary glow: `box-shadow: 0 0 20px --primary-glow`
- Hover glow: `box-shadow: 0 0 30px --primary-glow, 0 0 60px --primary-glow`
- Card hover: subtle top-border glow line
- Status indicators: pulsing dot glow for running scans

### Motion Philosophy

- **Page transitions**: Staggered fade-up (50ms delays between children)
- **Card hover**: translateY(-2px) + glow intensify (150ms ease-out)
- **Modal open**: scale(0.95) → scale(1) + fade (200ms spring)
- **Data loading**: Skeleton shimmer (1.5s linear infinite)
- **Micro-interactions**: Button press scale(0.97), toggle slides, badge pop

---

## Architecture

### File Structure (Post-Migration)

```
apps/web/
├── app/
│   ├── globals.css                    ← Tailwind directives + design tokens
│   ├── layout.tsx                     ← Fonts (Syne, Jakarta, JetBrains) + ThemeProvider
│   ├── page.tsx                       ← redirect (unchanged)
│   └── (dashboard)/
│       ├── layout.tsx                 ← Sidebar + CommandPalette + Toast
│       └── dashboard/
│           ├── page.tsx               ← Org list (overhauled)
│           └── [org_id]/
│               ├── page.tsx           ← Org overview
│               ├── settings/          ← Settings
│               ├── scorecard/         ← Scorecard
│               ├── audit-logs/        ← Audit logs
│               └── projects/[project_id]/
│                   ├── page.tsx       ← Project overview
│                   ├── findings/      ← Findings + drawer
│                   ├── scans/         ← Scans list + detail
│                   ├── repositories/  ← Repos + detail
│                   ├── exports/       ← Exports
│                   └── suppressions/  ← Suppressions
├── components/
│   ├── ui/                            ← shadcn/ui primitives
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── dropdown-menu.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── badge.tsx
│   │   ├── table.tsx
│   │   ├── skeleton.tsx
│   │   ├── toast.tsx
│   │   ├── toaster.tsx
│   │   ├── avatar.tsx
│   │   ├── tooltip.tsx
│   │   ├── command.tsx
│   │   ├── separator.tsx
│   │   ├── tabs.tsx
│   │   ├── scroll-area.tsx
│   │   ├── progress.tsx
│   │   ├── switch.tsx
│   │   ├── label.tsx
│   │   ├── textarea.tsx
│   │   └── popover.tsx
│   ├── scanforge/                     ← Project-specific components
│   │   ├── severity-badge.tsx         ← Severity indicator (dot + label + glow)
│   │   ├── status-badge.tsx           ← Scan/finding status pills
│   │   ├── stat-card.tsx              ← Metric card with icon + trend
│   │   ├── scorecard-ring.tsx         ← Circular grade indicator
│   │   ├── findings-table.tsx         ← Full findings table with sort/select
│   │   ├── finding-drawer.tsx         ← Detail slide-in panel
│   │   ├── trend-chart.tsx            ← SVG findings trend
│   │   ├── page-header.tsx            ← Consistent page header
│   │   ├── empty-state.tsx            ← Illustrated empty states
│   │   ├── sidebar.tsx                ← Enhanced sidebar
│   │   ├── breadcrumb.tsx             ← Breadcrumb component
│   │   ├── command-palette.tsx        ← Cmd+K global search
│   │   ├── filter-bar.tsx             ← Filter chips + search
│   │   ├── loading-skeleton.tsx       ← Page-specific skeletons
│   │   ├── notification-item.tsx      ← Single notification row
│   │   ├── onboarding-step.tsx        ← Onboarding checklist step
│   │   └── repo-health-card.tsx       ← Repository health indicator
│   └── providers/
│       ├── theme-provider.tsx         ← next-themes wrapper
│       └── toast-provider.tsx         ← Enhanced toast system
├── hooks/
│   ├── use-command-palette.ts         ← Cmd+K state management
│   ├── use-media-query.ts             ← Responsive breakpoint hook
│   └── use-keyboard-shortcut.ts       ← Keyboard shortcut registration
├── lib/
│   ├── utils.ts                       ← cn() utility (shadcn)
│   ├── api.ts                         ← API client (unchanged)
│   └── toast.tsx                      ← DEPRECATED (replaced by shadcn toast)
├── tailwind.config.ts                 ← Extended theme
├── postcss.config.mjs                 ← PostCSS config
└── components.json                    ← shadcn config
```

---

## Phase 1: Foundation — Tailwind + shadcn + Design Tokens

**Goal**: Bootstrap Tailwind CSS, install shadcn/ui, define the entire design system. App still works with old CSS during this phase.

### Step 1.1: Install Dependencies

```bash
cd apps/web
npm install -D tailwindcss @tailwindcss/postcss postcss
npm install tailwind-merge clsx class-variance-authority
npm install next-themes cmdk
npm install framer-motion
npx shadcn@latest init
```

shadcn init will create:
- `components.json` (config pointing to `@/components/ui`)
- `lib/utils.ts` (with `cn()` helper)
- `postcss.config.mjs`

### Step 1.2: Configure Tailwind Theme

**Create `apps/web/tailwind.config.ts`**:

```ts
import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        surface: {
          DEFAULT: "hsl(var(--surface))",
          hover: "hsl(var(--surface-hover))",
          elevated: "hsl(var(--surface-elevated))",
        },
        border: {
          DEFAULT: "hsl(var(--border))",
          strong: "hsl(var(--border-strong))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          glow: "hsl(var(--primary-glow))",
        },
        secondary: "hsl(var(--secondary))",
        accent: "hsl(var(--accent))",
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        danger: "hsl(var(--danger))",
        info: "hsl(var(--info))",
      },
      fontFamily: {
        display: ["var(--font-syne)"],
        sans: ["var(--font-jakarta)"],
        mono: ["var(--font-jetbrains)"],
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
        "slide-in-right": {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.95)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
        shimmer: "shimmer 1.5s linear infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "slide-in": "slide-in-right 0.3s ease-out",
        "scale-in": "scale-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
```

### Step 1.3: Rewrite `globals.css`

Replace current 80-line CSS with Tailwind directives + design token variables:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 220 25% 5%;
    --surface: 220 20% 9%;
    --surface-hover: 220 18% 12%;
    --surface-elevated: 220 16% 15%;
    --border: 220 15% 18%;
    --border-strong: 220 14% 24%;
    --text-primary: 210 20% 92%;
    --text-secondary: 215 14% 58%;
    --text-tertiary: 215 12% 38%;
    --primary: 217 91% 60%;
    --primary-glow: 217 91% 60%;
    --secondary: 263 70% 58%;
    --accent: 199 89% 48%;
    --success: 160 84% 39%;
    --warning: 38 92% 50%;
    --danger: 0 84% 60%;
    --info: 189 94% 43%;
    --radius: 0.5rem;
  }

  * {
    @apply border-border;
  }

  body {
    @apply bg-background text-text-primary antialiased;
    font-family: var(--font-jakarta);
    font-size: 14px;
    line-height: 1.6;
  }

  h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-syne);
  }

  code, pre, .mono {
    font-family: var(--font-jetbrains);
  }
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: hsl(var(--surface)); }
::-webkit-scrollbar-thumb { background: hsl(var(--border)); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: hsl(var(--text-tertiary)); }

::selection {
  background: hsl(var(--primary) / 0.2);
  color: hsl(var(--primary));
}
```

### Step 1.4: Update `layout.tsx` Fonts

```tsx
import { Syne, Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";

const syne = Syne({ subsets: ["latin"], variable: "--font-syne", display: "swap" });
const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-jakarta", display: "swap" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });

// Apply all three font variables to <html>
<html className={`${syne.variable} ${jakarta.variable} ${jetbrains.variable}`}>
```

### Step 1.5: Install shadcn Components

```bash
npx shadcn@latest add button card dialog input select badge table skeleton toast avatar tooltip command separator tabs scroll-area progress switch label textarea popover dropdown-menu
```

This creates 20+ files in `components/ui/`. All themed via CSS variables we just defined.

### Step 1.6: Create ThemeProvider + Toaster

**`components/providers/theme-provider.tsx`**: Wraps `next-themes` `ThemeProvider` with `dark` as default.

**`components/providers/toast-provider.tsx`**: Imports shadcn's `Toaster` component, replaces the old `lib/toast.tsx` context.

**Files created in Phase 1**:
| # | File | Action |
|---|------|--------|
| 1 | `tailwind.config.ts` | CREATE |
| 2 | `postcss.config.mjs` | CREATE (via shadcn init) |
| 3 | `components.json` | CREATE (via shadcn init) |
| 4 | `lib/utils.ts` | CREATE (via shadcn init) |
| 5 | `app/globals.css` | REWRITE |
| 6 | `app/layout.tsx` | REWRITE (fonts + providers) |
| 7 | `components/providers/theme-provider.tsx` | CREATE |
| 8 | `components/providers/toast-provider.tsx` | CREATE |
| 9-28 | `components/ui/*.tsx` | CREATE (20 shadcn components) |

---

## Phase 2: ScanForge Component Library

**Goal**: Build project-specific components on top of shadcn primitives. These replace the duplicated patterns across pages.

### 2.1 Severity System

**`components/scanforge/severity-badge.tsx`**
```
Props: severity: "critical" | "high" | "medium" | "low" | "info"

Visual: Dot indicator (pulsing for critical) + colored pill
- critical: red dot + red glow border + "CRITICAL" label
- high: orange dot + orange border
- medium: amber dot + amber border
- low: green dot + green border
- info: blue dot + blue border

Uses: shadcn Badge + custom glow CSS
```

**`components/scanforge/status-badge.tsx`**
```
Props: status: "open" | "fixed" | "suppressed" | "accepted_risk" | "duplicate"
       | "completed" | "failed" | "running" | "queued" | "canceled"

Visual: Pill with icon + label
- running: animated pulse dot
- completed: checkmark icon
- failed: X icon
```

### 2.2 Data Display

**`components/scanforge/stat-card.tsx`**
```
Props: icon, value, label, trend?, variant?

Visual: Card with icon (left), large value + small label (right)
Optional trend indicator (↑/↓ with color)
Variant border-left accent (green/red/amber/blue)
Uses: shadcn Card + custom styling
```

**`components/scanforge/scorecard-ring.tsx`**
```
Props: grade, overallScore, securityScore, secretsScore, dependencyScore

Visual: SVG ring indicator with grade letter center
Color-coded by grade (A=green, B=blue, C=amber, D=orange, F=red)
Score breakdown bars below ring
Uses: framer-motion for fill animation
```

**`components/scanforge/trend-chart.tsx`**
```
Props: data: { date: string; critical: number; high: number; ... }[]

Visual: SVG area chart with stacked severity layers
Gradient fills, hover tooltip
Replaces current basic SVG TrendChart
Uses: recharts or custom SVG with framer-motion
```

### 2.3 Layout Components

**`components/scanforge/page-header.tsx`**
```
Props: title, description, actions? (ReactNode), breadcrumbs?

Visual: Consistent page header with h1 (Syne font), subtitle, action buttons right-aligned
Replaces duplicated pageHeader patterns in every page
Uses: shadcn Button for actions
```

**`components/scanforge/empty-state.tsx`**
```
Props: icon | illustration, title, description, action?

Visual: Centered content with icon/illustration, heading, text, optional CTA
Uses: shadcn Button for CTA
```

**`components/scanforge/loading-skeleton.tsx`**
```
Exports: SkeletonTable, SkeletonCards, SkeletonStats, SkeletonList, SkeletonForm

Visual: Shimmer-animated placeholders matching each layout
Uses: shadcn Skeleton + custom composition
```

### 2.4 Navigation & Interaction

**`components/scanforge/sidebar.tsx`**
```
Refactored sidebar with:
- Org/project context display at top
- User avatar + dropdown (profile, settings, sign out)
- Collapsible sections with keyboard shortcuts
- Active state with glow indicator
- Notification count badge
Uses: shadcn Avatar, DropdownMenu, Tooltip, Badge
```

**`components/scanforge/command-palette.tsx`**
```
Triggered by Cmd+K / Ctrl+K
Searches: orgs, projects, findings, repos, nav items
Groups results by type with icons
Uses: shadcn Command (cmdk)
```

**`components/scanforge/breadcrumb.tsx`**
```
Auto-generates from pathname segments
Shows org name (not ID) when possible
Uses: shadcn primitives + Link
```

**`components/scanforge/filter-bar.tsx`**
```
Props: filters, onFilterChange, searchValue, onSearchChange

Visual: Search input (always visible) + filter chips (selected values as pills)
Collapsible "Advanced" panel for extra filters
Active filter count badge
Uses: shadcn Input, Badge, Popover, Button
```

### 2.5 Findings Components

**`components/scanforge/findings-table.tsx`**
```
Full findings table with:
- Sticky header
- Sort columns (severity, category, status, date)
- Row selection with checkbox
- Keyboard navigation (j/k)
- Click row to open drawer
- Severity dot indicators
- Age badges with color coding
Uses: shadcn Table, Checkbox, custom styling
```

**`components/scanforge/finding-drawer.tsx`**
```
Slide-in panel from right with:
- Tabs: Details, Instances, History, Related
- Finding title, severity, description
- Affected file locations (clickable)
- Action buttons (resolve, suppress)
Uses: shadcn Dialog (as drawer variant), Tabs, Button
```

**Files created in Phase 2**:
| # | File | Action |
|---|------|--------|
| 29 | `components/scanforge/severity-badge.tsx` | CREATE |
| 30 | `components/scanforge/status-badge.tsx` | CREATE |
| 31 | `components/scanforge/stat-card.tsx` | CREATE |
| 32 | `components/scanforge/scorecard-ring.tsx` | CREATE |
| 33 | `components/scanforge/trend-chart.tsx` | CREATE |
| 34 | `components/scanforge/page-header.tsx` | CREATE |
| 35 | `components/scanforge/empty-state.tsx` | CREATE |
| 36 | `components/scanforge/loading-skeleton.tsx` | CREATE |
| 37 | `components/scanforge/sidebar.tsx` | CREATE |
| 38 | `components/scanforge/command-palette.tsx` | CREATE |
| 39 | `components/scanforge/breadcrumb.tsx` | CREATE |
| 40 | `components/scanforge/filter-bar.tsx` | CREATE |
| 41 | `components/scanforge/findings-table.tsx` | CREATE |
| 42 | `components/scanforge/finding-drawer.tsx` | CREATE |
| 43 | `components/scanforge/notification-item.tsx` | CREATE |
| 44 | `components/scanforge/onboarding-step.tsx` | CREATE |
| 45 | `components/scanforge/repo-health-card.tsx` | CREATE |
| 46 | `components/scanforge/schedule-indicator.tsx` | CREATE |
| 47 | `hooks/use-command-palette.ts` | CREATE |
| 48 | `hooks/use-media-query.ts` | CREATE |
| 49 | `hooks/use-keyboard-shortcut.ts` | CREATE |

---

## Phase 3: Page-by-Page Overhaul

**Goal**: Rewrite every page using the new component library. Delete old CSS module files.

### Migration Order (by user-facing impact)

#### 3.1 Dashboard Layout Shell
**`app/(dashboard)/layout.tsx`** + **`app/(dashboard)/layout.module.css`**

- Replace `layout.module.css` with Tailwind classes
- Import new `Sidebar` component
- Import `CommandPalette` (triggered from header)
- Import `ThemeProvider` (already in root layout)
- Add `Toaster` to layout
- Header: sidebar toggle, breadcrumbs (new component), Cmd+K trigger, notification bell, user avatar dropdown
- **DELETE**: `layout.module.css`

#### 3.2 Organizations List (Dashboard Home)
**`app/(dashboard)/dashboard/page.tsx`** + **`page.module.css`**

- `PageHeader` component with title + "New Organization" button
- `StatCards` row showing org count, total findings, active scans
- Organization cards with: avatar (first letter), name, slug, grade badge, arrow
- Cards use Tailwind + hover glow effect
- Modal uses shadcn Dialog
- Search uses shadcn Input with icon
- Empty state uses `EmptyState` component
- Loading uses `SkeletonCards`
- **DELETE**: `page.module.css`

#### 3.3 Organization Page
**`app/(dashboard)/dashboard/[org_id]/page.tsx`** + **`page.module.css`**

- `PageHeader` with org name, member count, settings button
- Stats row: 3 `StatCard` components
- Project list: cards with folder icon, name, description, badges
- Activity feed: timeline with dots
- Create project modal: shadcn Dialog + Form
- **DELETE**: `page.module.css`

#### 3.4 Project Overview
**`app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`** + **`page.module.css`**

- `PageHeader` with project name, "Connect Repository" button
- 4 `StatCard` components (open, critical, fixed, suppressed)
- Severity pills row (clickable, link to filtered findings)
- `ScorecardRing` component (replaces inline grade ring)
- `TrendChart` component (replaces basic SVG)
- Two-column layout: Recent Scans + Quick Links
- `RepoHealthCard` grid
- `ScheduleIndicator` component
- **DELETE**: `page.module.css`, `TrendChart.module.css`

#### 3.5 Findings Page (Most Complex)
**`app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`** + **`page.module.css`**

- `PageHeader` with title, total count, export buttons
- `FilterBar` with search + severity/category/status/repo/scanner chips
- `FindingsTable` component (replaces 200-line inline table)
- Bulk action bar (appears when items selected)
- Pagination using shadcn Button
- `FindingDrawer` component (replaces inline drawer)
- `LoadingSkeleton` for table
- **DELETE**: `page.module.css`, `FindingDrawer.module.css`

#### 3.6 Scans Pages
**`scans/page.tsx`** + **`scans/[scan_id]/page.tsx`** + CSS files

- Scan list with status indicators, filter by status
- Scan detail with findings breakdown, timeline
- Status badges with animated running indicator
- **DELETE**: both `.module.css` files

#### 3.7 Repositories Pages
**`repositories/page.tsx`** + **`repositories/[repo_id]/page.tsx`** + **`ScheduleSection.tsx`** + CSS files

- GitHub repo picker (shadcn Dialog + search)
- Repository cards with health indicators
- Schedule management with shadcn form components
- **DELETE**: all 3 `.module.css` files

#### 3.8 Remaining Pages
- **Settings**: Form layout with shadcn Input, Switch, Label
- **Scorecard**: Enhanced scorecard ring + breakdown
- **Audit Logs**: Table with filters
- **Exports**: Card grid with download actions
- **Suppressions**: Table with rule management
- **Notifications**: List with filter, mark-read actions
- **Profile**: User card + notification preferences (shadcn Switch)
- **Onboarding**: Progress bar + step cards with animations

**DELETE**: all remaining `.module.css` files

### Old Files Deleted in Phase 3

| # | File | Reason |
|---|------|--------|
| 50 | `app/(dashboard)/layout.module.css` | Replaced by Tailwind |
| 51 | `app/(dashboard)/dashboard/page.module.css` | Replaced by Tailwind |
| 52 | `app/(dashboard)/dashboard/[org_id]/page.module.css` | Replaced by Tailwind |
| 53 | `app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.module.css` | Replaced |
| 54 | `.../projects/[project_id]/TrendChart.module.css` | Merged into component |
| 55 | `.../projects/[project_id]/findings/page.module.css` | Replaced |
| 56 | `.../findings/FindingDrawer.module.css` | Replaced |
| 57 | `.../projects/[project_id]/exports/page.module.css` | Replaced |
| 58 | `.../projects/[project_id]/repositories/page.module.css` | Replaced |
| 59 | `.../repositories/[repo_id]/page.module.css` | Replaced |
| 60 | `.../repositories/ScheduleSection.module.css` | Replaced |
| 61 | `.../projects/[project_id]/suppressions/page.module.css` | Replaced |
| 62 | `.../projects/[project_id]/scans/page.module.css` | Replaced |
| 63 | `.../scans/[scan_id]/page.module.css` | Replaced |
| 64 | `.../notifications/page.module.css` | Replaced |
| 65 | `.../onboarding/page.module.css` | Replaced |
| 66 | `.../profile/page.module.css` | Replaced |
| 67 | `lib/toast.tsx` | Replaced by shadcn toast |

---

## Phase 4: Polish & Motion

**Goal**: Add animations, responsive design, and final UX improvements.

### 4.1 Page Enter Animations

Every page gets staggered children animations using framer-motion:

```tsx
import { motion } from "framer-motion";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};
```

- Page header: immediate fade-in
- Cards/sections: staggered 50ms apart
- Table rows: cascade from top

### 4.2 Micro-Interactions

- Button press: `scale(0.97)` on click
- Card hover: `translateY(-2px)` + glow shadow
- Badge appear: `scale(0) → scale(1)` pop
- Sidebar collapse: smooth width transition
- Modal backdrop: blur + fade
- Severity dot pulse: CSS animation for critical items

### 4.3 Responsive Design

**Breakpoints**:
- `sm` (640px): Tablet portrait — stack stat cards 2-col
- `md` (768px): Tablet landscape — sidebar becomes overlay
- `lg` (1024px): Desktop — full sidebar + 2-col layouts
- `xl` (1280px): Wide — wider content areas

**Key responsive changes**:
- Sidebar: overlay drawer on mobile (triggered by hamburger)
- Findings table: scroll horizontally on small screens OR convert to card layout
- Stat cards: 4-col → 2-col → 1-col
- Two-column layouts: stack vertically
- Filter bar: collapse to single row with "Filters" expand button
- Page header actions: overflow into dropdown menu

### 4.4 Keyboard Shortcuts

- `Cmd/Ctrl + K`: Command palette
- `/`: Focus search on current page
- `N`: New (context-aware: org, project, etc.)
- `J/K`: Navigate findings table
- `Enter`: Open selected finding
- `Escape`: Close drawer/modal/palette
- `?`: Show keyboard shortcuts help modal

### 4.5 Dark/Light Mode Foundation

While the platform defaults to dark mode, add infrastructure for light mode:
- All colors defined as HSL variables
- `next-themes` with `class` strategy
- Toggle in user dropdown menu
- Light mode palette: reverse the background hierarchy, maintain accent colors

---

## Phase Dependencies

```
Phase 1 (Foundation)
  │
  ├── Tailwind installed, config ready
  ├── shadcn components installed
  ├── Design tokens defined
  ├── Fonts configured
  │
  ▼
Phase 2 (Component Library)
  │
  ├── All ScanForge components built
  ├── Tested in isolation
  │
  ▼
Phase 3 (Page Overhaul)
  │
  ├── Pages migrated one by one
  ├── Old CSS modules deleted
  ├── Toast system wired up
  │
  ▼
Phase 4 (Polish)
  │
  ├── Animations added
  ├── Responsive breakpoints
  ├── Keyboard shortcuts
  └── Final QA pass
```

**Can be parallelized**:
- Phase 2 components can be built while Phase 1 pages are still using old CSS
- Phase 3 pages can be migrated in any order (layout shell first)
- Phase 4 polish can be layered on during Phase 3

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| CSS strategy | Tailwind CSS | Industry standard, shadcn requirement, utility-first speed |
| Component library | shadcn/ui | Copy-paste, customizable, Radix accessibility, no lock-in |
| Animation | Framer Motion | React 19 compatible, spring physics, layout animations |
| Theme | next-themes | Class-based, no flash, SSR-safe |
| Command palette | cmdk | Used by shadcn Command, battle-tested |
| Icons | Lucide (keep) | shadcn uses Lucide by default, zero migration cost |
| Fonts | Syne + Jakarta + JetBrains | Distinctive, Google Fonts, performance-optimized |
| CSS Modules | Deleted | Fully replaced by Tailwind utility classes |
| Toast | shadcn toast | Replaces hand-rolled toast.tsx |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Tailwind + CSS Modules conflict during migration | Migrate layout shell first, then pages. CSS Modules coexist until deleted. |
| shadcn components don't match aesthetic | Every shadcn component is customizable — extend via `cn()` and theme variables |
| Font loading performance | `next/font/google` with `display: swap` + preconnect |
| Breaking existing functionality | Pages use same API client, same routing. Only UI changes. |
| Bundle size increase | Tailwind purges unused classes. Framer Motion tree-shaken. shadcn is zero-runtime. |
