"use client";

import Link from "next/link";
import { Bell, LogOut, User, X } from "lucide-react";

import { authClient } from "@/lib/auth/client";
import { type DashboardNavigationModel, type DashboardNavItem } from "@/lib/dashboard-navigation";
import { cn } from "@/lib/utils";

import { ScanForgeLogo } from "./logo";

interface SidebarNavProps {
  isMobile: boolean;
  open: boolean;
  unreadCount: number;
  pathname: string;
  navigation: DashboardNavigationModel;
  onCloseMobile: () => void;
}

export function SidebarNav({
  isMobile,
  open,
  unreadCount,
  pathname,
  navigation,
  onCloseMobile,
}: SidebarNavProps) {
  const showLabels = isMobile || open;
  const unread = unreadCount > 99 ? "99+" : unreadCount > 0 ? `${unreadCount}` : null;

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-screen flex-col border-r border-border bg-surface transition-transform duration-200 ease-[var(--ease-drawer)]",
        showLabels ? "w-[220px]" : "w-16",
        isMobile && !open && "-translate-x-full"
      )}
    >
      <div className="flex h-14 shrink-0 items-center px-2">
        <div className={rowClass(false, showLabels)}>
          <ScanForgeLogo className="h-4 w-4 shrink-0" />
          {showLabels ? <span className="truncate text-sm font-medium">ScanForge</span> : null}
        </div>
        {isMobile ? (
          <button
            type="button"
            onClick={onCloseMobile}
            className="ml-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-text-secondary"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-2 py-2">
        <NavGroup label="Work" items={navigation.work} pathname={pathname} showLabels={showLabels} onNavigate={onCloseMobile} />
        {navigation.setup.length > 0 ? (
          <NavGroup label="Setup" items={navigation.setup} pathname={pathname} showLabels={showLabels} onNavigate={onCloseMobile} />
        ) : null}
      </nav>

      <div className="flex shrink-0 flex-col gap-0.5 border-t border-border px-2 py-2">
        <FooterLink href="/profile" icon={User} label="Profile" pathname={pathname} showLabels={showLabels} onNavigate={onCloseMobile} />
        <FooterLink
          href="/notifications"
          icon={Bell}
          label="Notifications"
          pathname={pathname}
          showLabels={showLabels}
          badge={unread}
          onNavigate={onCloseMobile}
        />
        <button type="button" onClick={() => authClient.signOut()} className={rowClass(false, showLabels)}>
          <LogOut className="h-4 w-4 shrink-0" />
          {showLabels ? <span className="truncate">Sign out</span> : null}
        </button>
      </div>
    </aside>
  );
}

function NavGroup({
  label,
  items,
  pathname,
  showLabels,
  onNavigate,
}: {
  label: string;
  items: DashboardNavItem[];
  pathname: string;
  showLabels: boolean;
  onNavigate: () => void;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      {showLabels ? <p className="px-2 pb-1 pl-9 text-xs text-text-tertiary">{label}</p> : null}
      {items.map((item) => {
        const active = item.href ? isActive(pathname, item.href) : false;
        const content = (
          <div className={rowClass(active, showLabels, item.disabled)}>
            <item.icon className="h-4 w-4 shrink-0" />
            {showLabels ? <span className="truncate">{item.label}</span> : null}
          </div>
        );
        if (item.disabled || !item.href) {
          return <div key={item.label}>{content}</div>;
        }
        return (
          <Link key={item.label} href={item.href} onClick={onNavigate}>
            {content}
          </Link>
        );
      })}
    </div>
  );
}

function FooterLink({
  href,
  icon: Icon,
  label,
  pathname,
  showLabels,
  badge,
  onNavigate,
}: {
  href: string;
  icon: typeof User;
  label: string;
  pathname: string;
  showLabels: boolean;
  badge?: string | null;
  onNavigate: () => void;
}) {
  return (
    <Link href={href} onClick={onNavigate}>
      <div className={rowClass(isActive(pathname, href), showLabels)}>
        <span className="relative shrink-0">
          <Icon className="h-4 w-4" />
          {badge && !showLabels ? <span className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-primary" /> : null}
        </span>
        {showLabels ? <span className="truncate">{label}</span> : null}
        {badge && showLabels ? (
          <span className="ml-auto font-mono text-[11px] text-primary">{badge}</span>
        ) : null}
      </div>
    </Link>
  );
}

function rowClass(active: boolean, showLabels: boolean, disabled = false) {
  return cn(
    "flex h-9 items-center rounded-md text-sm",
    showLabels ? "gap-2 px-2" : "w-12 justify-center",
    disabled
      ? "cursor-not-allowed text-text-tertiary/40"
      : active
        ? "bg-surface-hover text-text-primary"
        : "text-text-secondary hover-fine:bg-surface-hover hover-fine:text-text-primary"
  );
}

function isActive(pathname: string, href: string) {
  if (href === "/dashboard" || href === "/notifications" || href === "/profile") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}
