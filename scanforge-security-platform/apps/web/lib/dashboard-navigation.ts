import {
  Activity,
  Building2,
  Database,
  FileText,
  LayoutDashboard,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";

export interface DashboardNavItem {
  icon: typeof LayoutDashboard;
  label: string;
  href: string | null;
  disabled: boolean;
}

export interface DashboardNavigationModel {
  context: {
    orgId: string | null;
    projectId: string | null;
  };
  work: DashboardNavItem[];
  setup: DashboardNavItem[];
  account: DashboardNavItem[];
}

/**
 * Project-scoped destinations stay reachable from an org route by resolving
 * the current project. Work items are disabled only when no org is selected.
 */
export function buildDashboardNavigation(
  pathname: string,
  projectIdOverride: string | null = null
): DashboardNavigationModel {
  const segments = pathname.split("/").filter(Boolean);
  const orgId = segments[0] === "dashboard" && segments.length > 1 ? segments[1] : null;
  const routeProjectId = segments[2] === "projects" && segments.length > 3 ? segments[3] : null;
  const projectId = routeProjectId ?? projectIdOverride;

  const projectHref = (leaf: string) =>
    orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/${leaf}` : null;

  return {
    context: { orgId, projectId },
    work: [
      navItem(LayoutDashboard, "Overview", "/dashboard", false),
      navItem(Building2, "Organization", orgId ? `/dashboard/${orgId}` : "/dashboard", false),
      navItem(Search, "Open findings", projectHref("findings"), !(orgId && projectId)),
      navItem(Activity, "Scans", projectHref("scans"), !(orgId && projectId)),
    ],
    setup: orgId
      ? [
          navItem(Database, "Repositories", projectHref("repositories"), !projectId),
          navItem(ShieldCheck, "Suppressions", projectHref("suppressions"), !projectId),
          navItem(FileText, "Exports", projectHref("exports"), !projectId),
          navItem(FileText, "Audit log", `/dashboard/${orgId}/audit-logs`, false),
          navItem(Settings, "Settings", `/dashboard/${orgId}/settings`, false),
        ]
      : [],
    account: [],
  };
}

function navItem(
  icon: typeof LayoutDashboard,
  label: string,
  href: string | null,
  disabled: boolean
): DashboardNavItem {
  return { icon, label, href, disabled };
}
