"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AppShell } from "@/components/scanforge/app-shell";
import { useIsMobile } from "@/hooks/use-media-query";
import { api } from "@/lib/api";
import { buildDashboardNavigation } from "@/lib/dashboard-navigation";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    setSidebarOpen(!isMobile);
  }, [isMobile]);

  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    }
  }, [pathname, isMobile]);

  useEffect(() => {
    let cancelled = false;

    async function fetchUnread() {
      try {
        const res = await api.notifications.unreadCount();
        if (!cancelled) {
          setUnreadCount(res.unread_count ?? 0);
        }
      } catch {
        if (!cancelled) {
          setUnreadCount(0);
        }
      }
    }

    fetchUnread();
    const interval = window.setInterval(fetchUnread, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const navigation = buildDashboardNavigation(pathname);

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
