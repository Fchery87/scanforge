"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useIsMobile } from "@/hooks/use-media-query";
import { Breadcrumb } from "@/components/scanforge/breadcrumb";
import { CommandPalette } from "@/components/scanforge/command-palette";
import { KeyboardShortcutsModal } from "@/components/scanforge/keyboard-shortcuts-modal";
import { ScanForgeLogo } from "@/components/scanforge/logo";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Shield,
  Building2,
  LayoutDashboard,
  Search,
  Activity,
  Database,
  FileText,
  Settings,
  Bell,
  LogOut,
  ChevronRight,
  ChevronLeft,
  BarChart3,
  ShieldCheck,
  User,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
    else setSidebarOpen(true);
  }, [isMobile]);

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [pathname, isMobile]);

  useEffect(() => {
    function fetchUnread() {
      api.notifications.unreadCount()
        .then((res) => setUnreadCount(res.unread_count ?? 0))
        .catch(() => {});
    }
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, []);

  const segments = pathname.split("/").filter(Boolean);
  const orgId = segments[0] === "dashboard" && segments.length > 1 ? segments[1] : null;
  const projectId = segments[2] === "projects" && segments.length > 3 ? segments[3] : null;

  function isActive(href: string) {
    if (href === "/dashboard") return pathname === "/dashboard";
    if (href === "/notifications") return pathname === "/notifications";
    return pathname.startsWith(href);
  }

  const navItems = [
    { icon: LayoutDashboard, label: "Overview", href: "/dashboard", available: true },
    { icon: Building2, label: "Organizations", href: orgId ? `/dashboard/${orgId}` : "/dashboard", available: true },
    { icon: Search, label: "Findings", href: orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/findings` : null, available: !!(orgId && projectId) },
    { icon: Activity, label: "Scans", href: orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/scans` : null, available: !!(orgId && projectId) },
    { icon: Database, label: "Repositories", href: orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/repositories` : null, available: !!(orgId && projectId) },
    { icon: FileText, label: "Exports", href: orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/exports` : null, available: !!(orgId && projectId) },
    { icon: BarChart3, label: "Scorecard", href: orgId ? `/dashboard/${orgId}/scorecard` : null, available: !!orgId },
    { icon: ShieldCheck, label: "Suppressions", href: orgId && projectId ? `/dashboard/${orgId}/projects/${projectId}/suppressions` : null, available: !!(orgId && projectId) },
  ];

  const navItemClass = (href: string | null, isDisabled = false) =>
    cn(
      "flex items-center gap-3 px-3 py-2 text-[13px] font-medium transition-colors border-l-2",
      isDisabled
        ? "opacity-30 cursor-not-allowed pointer-events-none text-text-secondary border-transparent"
        : href && isActive(href)
          ? "bg-surface-hover text-text-primary border-accent"
          : "text-text-secondary hover:bg-surface-hover hover:text-text-primary border-transparent hover:border-border-strong"
    );

  const handleNavClick = useCallback(() => {
    if (isMobile) setSidebarOpen(false);
  }, [isMobile]);

  const sidebarWidth = isMobile ? "w-[272px]" : sidebarOpen ? "w-[260px]" : "w-[68px]";
  const mainMargin = isMobile ? "ml-0" : sidebarOpen ? "ml-[260px]" : "ml-[68px]";
  const showLabels = isMobile || sidebarOpen;

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex min-h-screen bg-background relative z-10">
        {/* Mobile backdrop */}
        {isMobile && sidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm animate-fade-in"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={cn(
            "fixed left-0 top-0 z-50 flex h-screen flex-col bg-surface border-r border-border transition-all duration-200 ease-out",
            sidebarWidth,
            isMobile && !sidebarOpen && "-translate-x-full"
          )}
        >
          {/* Active indicator strip on right edge */}
          <div className="absolute top-0 right-0 bottom-0 w-px bg-gradient-to-b from-primary/25 via-primary/8 to-transparent pointer-events-none" />

          {/* Logo */}
          <div className="flex items-center gap-3 border-b border-border px-4 h-14">
            <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-border-strong bg-surface text-accent flex-shrink-0 shadow-[0_0_10px_rgba(0,229,255,0.1)]">
              <ScanForgeLogo className="h-4 w-4" />
            </div>
            {showLabels && (
              <div className="flex flex-col overflow-hidden animate-fade-in flex-1 min-w-0">
                <span className="text-sm font-bold tracking-tight">ScanForge</span>
                <span className="text-[10px] text-text-tertiary font-mono uppercase tracking-wider">security</span>
              </div>
            )}
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="flex h-7 w-7 items-center justify-center rounded-md text-text-tertiary hover:text-text-primary hover:bg-surface-hover transition-colors ml-auto"
              >
                <X size={16} />
              </button>
            )}
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
            {navItems.map((item) => {
              const NavContent = (
                <div className={navItemClass(item.href, !item.available)}>
                  <item.icon size={16} strokeWidth={1.25} className="flex-shrink-0" />
                  {showLabels && <span className="truncate">{item.label}</span>}
                </div>
              );

              if (!item.href) {
                return (
                  <Tooltip key={item.label}>
                    <TooltipTrigger asChild>{NavContent}</TooltipTrigger>
                    {!showLabels && <TooltipContent side="right" sideOffset={8}>{item.label}</TooltipContent>}
                  </Tooltip>
                );
              }

              return (
                <Tooltip key={item.label}>
                  <TooltipTrigger asChild>
                    <Link href={item.href} onClick={handleNavClick}>{NavContent}</Link>
                  </TooltipTrigger>
                  {!showLabels && <TooltipContent side="right" sideOffset={8}>{item.label}</TooltipContent>}
                </Tooltip>
              );
            })}

            {/* Organization section */}
            {orgId && (
              <>
                {showLabels && (
                  <div className="px-3 pt-5 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                    Organization
                  </div>
                )}
                {!showLabels && <div className="my-3 mx-3 border-t border-border" />}

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link href={`/dashboard/${orgId}/audit-logs`} onClick={handleNavClick}>
                      <div className={navItemClass(`/dashboard/${orgId}/audit-logs`)}>
                        <FileText size={16} strokeWidth={1.25} className="flex-shrink-0" />
                        {showLabels && <span>Audit Log</span>}
                      </div>
                    </Link>
                  </TooltipTrigger>
                  {!showLabels && <TooltipContent side="right" sideOffset={8}>Audit Log</TooltipContent>}
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link href={`/dashboard/${orgId}/settings`} onClick={handleNavClick}>
                      <div className={navItemClass(`/dashboard/${orgId}/settings`)}>
                        <Settings size={16} strokeWidth={1.25} className="flex-shrink-0" />
                        {showLabels && <span>Settings</span>}
                      </div>
                    </Link>
                  </TooltipTrigger>
                  {!showLabels && <TooltipContent side="right" sideOffset={8}>Settings</TooltipContent>}
                </Tooltip>
              </>
            )}
          </nav>

          {/* Footer */}
          <div className="border-t border-border py-2 px-2 space-y-0.5">
            <Tooltip>
              <TooltipTrigger asChild>
                <Link href="/profile" onClick={handleNavClick}>
                  <div className={navItemClass("/profile")}>
                    <User size={16} strokeWidth={1.25} className="flex-shrink-0" />
                    {showLabels && <span>Profile</span>}
                  </div>
                </Link>
              </TooltipTrigger>
              {!showLabels && <TooltipContent side="right" sideOffset={8}>Profile</TooltipContent>}
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Link href="/notifications" onClick={handleNavClick}>
                  <div className={navItemClass("/notifications")}>
                    <div className="relative flex-shrink-0">
                      <Bell size={16} strokeWidth={1.25} />
                      {unreadCount > 0 && (
                        <span className="absolute -top-1.5 -right-1.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary text-[9px] font-bold text-white px-1">
                          {unreadCount > 99 ? "99+" : unreadCount}
                        </span>
                      )}
                    </div>
                    {showLabels && <span>Notifications</span>}
                  </div>
                </Link>
              </TooltipTrigger>
              {!showLabels && <TooltipContent side="right" sideOffset={8}>Notifications</TooltipContent>}
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <button className={cn(navItemClass("/dashboard"), "w-full text-left")}>
                  <LogOut size={16} strokeWidth={1.25} className="flex-shrink-0" />
                  {showLabels && <span>Sign Out</span>}
                </button>
              </TooltipTrigger>
              {!showLabels && <TooltipContent side="right" sideOffset={8}>Sign Out</TooltipContent>}
            </Tooltip>
          </div>
        </aside>

        {/* Main area */}
        <div className={cn("flex flex-1 flex-col transition-all duration-200 ease-out relative z-10", mainMargin)}>
          {/* Header */}
          <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border/50 bg-background/80 backdrop-blur-xl px-5">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
              aria-label="Toggle sidebar"
            >
              {isMobile ? (
                <Menu size={16} />
              ) : sidebarOpen ? (
                <ChevronLeft size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
            </button>

            <Breadcrumb className="flex-1 hidden sm:flex" />

            <div className="flex items-center gap-1.5">
              <div className="hidden md:block">
                <CommandPalette />
              </div>
              <KeyboardShortcutsModal />
              <Link
                href="/notifications"
                className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
                aria-label="Notifications"
              >
                <Bell size={16} strokeWidth={1.75} />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-primary border-2 border-background animate-glow-pulse" />
                )}
              </Link>
            </div>
          </header>

          {/* Content */}
          <main className="flex-1 p-5 md:p-6 lg:p-8">
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
