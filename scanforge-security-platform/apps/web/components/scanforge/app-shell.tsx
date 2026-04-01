"use client";

import { cn } from "@/lib/utils";

import { type DashboardNavigationModel } from "@/lib/dashboard-navigation";

import { SidebarNav } from "./sidebar-nav";
import { TopBar } from "./top-bar";
import { SectionFrame } from "./section-frame";

interface AppShellProps {
  children: React.ReactNode;
  isMobile: boolean;
  sidebarOpen: boolean;
  unreadCount: number;
  pathname: string;
  navigation: DashboardNavigationModel;
  onToggleSidebar: () => void;
  onCloseMobile: () => void;
}

export function AppShell({
  children,
  isMobile,
  sidebarOpen,
  unreadCount,
  pathname,
  navigation,
  onToggleSidebar,
  onCloseMobile,
}: AppShellProps) {
  const sidebarWidth = isMobile ? 0 : sidebarOpen ? 286 : 88;

  return (
    <div className="min-h-screen bg-background">
      {isMobile && sidebarOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={onCloseMobile}
        />
      ) : null}

      <SidebarNav
        isMobile={isMobile}
        open={sidebarOpen}
        unreadCount={unreadCount}
        pathname={pathname}
        navigation={navigation}
        onCloseMobile={onCloseMobile}
      />

      <div
        className={cn(
          "flex min-h-screen flex-col transition-[margin] duration-[var(--duration-base)] ease-[var(--ease-out-expo)]"
        )}
        style={{ marginLeft: sidebarWidth }}
      >
        <TopBar
          isMobile={isMobile}
          sidebarOpen={sidebarOpen}
          unreadCount={unreadCount}
          onToggleSidebar={onToggleSidebar}
        />
        <SectionFrame>{children}</SectionFrame>
      </div>
    </div>
  );
}
