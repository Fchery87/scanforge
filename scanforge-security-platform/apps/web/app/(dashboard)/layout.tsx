"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AppShell } from "@/components/scanforge/app-shell";
import { useIsMobile } from "@/hooks/use-media-query";
import { api } from "@/lib/api";
import { buildDashboardNavigation } from "@/lib/dashboard-navigation";

const PROJECT_KEY = "scanforge:last-project";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [resolvedProjectId, setResolvedProjectId] = useState<string | null>(null);

  useEffect(() => {
    setSidebarOpen(!isMobile);
  }, [isMobile]);

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [pathname, isMobile]);

  useEffect(() => {
    let cancelled = false;
    async function fetchUnread() {
      try {
        const res = await api.notifications.unreadCount();
        if (!cancelled) setUnreadCount(res.unread_count ?? 0);
      } catch {
        if (!cancelled) setUnreadCount(0);
      }
    }
    fetchUnread();
    const interval = window.setInterval(fetchUnread, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const segments = pathname.split("/").filter(Boolean);
    const orgId = segments[0] === "dashboard" && segments.length > 1 ? segments[1] : null;
    const routeProjectId = segments[2] === "projects" && segments.length > 3 ? segments[3] : null;

    if (routeProjectId && orgId) {
      window.localStorage.setItem(PROJECT_KEY, JSON.stringify({ orgId, projectId: routeProjectId }));
      setResolvedProjectId(routeProjectId);
      return;
    }

    if (!orgId) {
      setResolvedProjectId(null);
      return;
    }

    const remembered = readRememberedProject(orgId);
    if (remembered) {
      setResolvedProjectId(remembered);
      return;
    }

    let cancelled = false;
    api.projects
      .list(orgId, 0, 1)
      .then((res) => {
        if (cancelled) return;
        const first = res.items?.[0]?.id ?? null;
        setResolvedProjectId(first);
        if (first) {
          window.localStorage.setItem(PROJECT_KEY, JSON.stringify({ orgId, projectId: first }));
        }
      })
      .catch(() => {
        if (!cancelled) setResolvedProjectId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const navigation = buildDashboardNavigation(pathname, resolvedProjectId);

  return (
    <AppShell
      isMobile={isMobile}
      sidebarOpen={sidebarOpen}
      unreadCount={unreadCount}
      pathname={pathname}
      navigation={navigation}
      onToggleSidebar={() => setSidebarOpen((current) => !current)}
      onCloseMobile={() => setSidebarOpen(false)}
    >
      {children}
    </AppShell>
  );
}

function readRememberedProject(orgId: string) {
  try {
    const raw = window.localStorage.getItem(PROJECT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { orgId?: string; projectId?: string };
    return parsed.orgId === orgId ? parsed.projectId ?? null : null;
  } catch {
    return null;
  }
}
