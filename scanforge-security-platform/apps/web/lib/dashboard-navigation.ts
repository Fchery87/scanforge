import {
  Activity,
  BarChart3,
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
  primary: DashboardNavItem[];
  secondary: DashboardNavItem[];
}

export function buildDashboardNavigation(pathname: string): DashboardNavigationModel {
  const segments = pathname.split("/").filter(Boolean);
  const orgId = segments[0] === "dashboard" && segments.length > 1 ? segments[1] : null;
  const projectId = segments[2] === "projects" && segments.length > 3 ? segments[3] : null;

  return {
    context: { orgId, projectId },
    primary: [
      navItem(LayoutDashboard, "Overview", "/dashboard", false),
      navItem(Building2, "Organizations", orgId ? `/dashboard/${orgId}` : "/dashboard", false),
      navItem(
        Search,
        "Findings",
        orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/findings` : null,
        !(orgId && projectId)
      ),
      navItem(
        Activity,
        "Scans",
        orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/scans` : null,
        !(orgId && projectId)
      ),
      navItem(
        Database,
        "Repositories",
        orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/repositories` : null,
        !(orgId && projectId)
      ),
      navItem(
        FileText,
        "Exports",
        orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/exports` : null,
        !(orgId && projectId)
      ),
      navItem(
        BarChart3,
        "Scorecard",
        orgId ? `/dashboard/${orgId}/scorecard` : null,
        !orgId
      ),
      navItem(
        ShieldCheck,
        "Suppressions",
        orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/suppressions` : null,
        !(orgId && projectId)
      ),
    ],
    secondary: orgId
      ? [
          navItem(FileText, "Audit Log", `/dashboard/${orgId}/audit-logs`, false),
          navItem(Settings, "Settings", `/dashboard/${orgId}/settings`, false),
        ]
      : [],
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
