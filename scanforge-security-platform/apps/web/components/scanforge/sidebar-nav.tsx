"use client";

import Link from "next/link";
import { Bell, LogOut, User, X } from "lucide-react";

import { authClient } from "@/lib/auth/client";
import { type DashboardNavigationModel } from "@/lib/dashboard-navigation";
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
  const { orgId } = navigation.context;
  const showLabels = isMobile || open;

  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-50 flex h-screen flex-col border-r border-border bg-surface/95 backdrop-blur-xl transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-expo)]",
        showLabels ? "w-[286px]" : "w-[88px]",
        isMobile && !open && "-translate-x-full",
      )}
    >
      <div className="flex h-20 items-center gap-4 border-b border-border px-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
          <ScanForgeLogo className="h-5 w-5" />
        </div>
        {showLabels ? (
          <div className="min-w-0 flex-1">
            <p className="font-display text-[1.6rem] leading-none tracking-[-0.03em] text-text-primary">
              ScanForge
            </p>
            <p className="mt-1 font-mono text-[0.68rem] uppercase tracking-[0.18em] text-text-tertiary">
              Security Operations
            </p>
          </div>
        ) : null}
        {isMobile ? (
          <button
            type="button"
            onClick={onCloseMobile}
            className="ml-auto flex h-10 w-10 items-center justify-center rounded-[8px] border border-border bg-surface-elevated text-text-secondary transition-colors hover:text-text-primary"
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <NavGroup
          items={navigation.primary}
          pathname={pathname}
          showLabels={showLabels}
          onNavigate={onCloseMobile}
        />

        {navigation.secondary.length > 0 ? (
          <>
            <div className={cn("my-4", showLabels ? "px-3" : "px-2")}>
              <div className="divider-serif" />
            </div>
            {showLabels ? (
              <p className="px-3 pb-2 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-text-tertiary">
                Organization
              </p>
            ) : null}
            <NavGroup
              items={navigation.secondary}
              pathname={pathname}
              showLabels={showLabels}
              onNavigate={onCloseMobile}
            />
          </>
        ) : null}
      </nav>

      <div className="border-t border-border px-3 py-3">
        <div className="space-y-1">
          <FooterLink
            href="/profile"
            icon={User}
            label="Profile"
            pathname={pathname}
            showLabels={showLabels}
            onNavigate={onCloseMobile}
          />
          <FooterLink
            href="/notifications"
            icon={Bell}
            label="Notifications"
            pathname={pathname}
            showLabels={showLabels}
            badge={unreadCount > 0 ? (unreadCount > 99 ? "99+" : `${unreadCount}`) : null}
            onNavigate={onCloseMobile}
          />
          <button
            type="button"
            onClick={() => authClient.signOut()}
            className={navButtonClass(false)}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {showLabels ? <span>Sign Out</span> : null}
          </button>
        </div>
        {showLabels && orgId ? (
          <p className="mt-4 px-3 font-mono text-[0.68rem] uppercase tracking-[0.16em] text-text-tertiary">
            Org: {orgId}
          </p>
        ) : null}
      </div>
    </aside>
  );
}

function NavGroup({
  items,
  pathname,
  showLabels,
  onNavigate,
}: {
  items: DashboardNavigationModel["primary"];
  pathname: string;
  showLabels: boolean;
  onNavigate: () => void;
}) {
  return (
    <div className="space-y-1">
      {items.map((item) => {
        const active = item.href ? isActive(pathname, item.href) : false;
        const content = (
          <div className={navButtonClass(active, item.disabled)}>
            <item.icon className="h-4 w-4 shrink-0" />
            {showLabels ? <span className="truncate">{item.label}</span> : null}
          </div>
        );

        if (item.disabled || !item.href) {
          return (
            <div key={item.label} aria-disabled="true">
              {content}
            </div>
          );
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
      <div className={navButtonClass(isActive(pathname, href))}>
        <div className="relative shrink-0">
          <Icon className="h-4 w-4" />
          {badge ? (
            <span className="absolute -right-2 -top-2 flex min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[9px] font-semibold text-background">
              {badge}
            </span>
          ) : null}
        </div>
        {showLabels ? <span>{label}</span> : null}
      </div>
    </Link>
  );
}

function navButtonClass(active: boolean, disabled = false) {
  return cn(
    "flex min-h-11 items-center gap-3 rounded-[10px] border px-3 text-[0.84rem] font-medium transition-all duration-[var(--duration-fast)] ease-[var(--ease-out-expo)]",
    disabled
      ? "cursor-not-allowed border-transparent text-text-tertiary/50 opacity-60"
      : active
        ? "border-border-strong bg-primary/10 text-text-primary shadow-[inset_0_1px_0_rgba(243,238,231,0.03)]"
        : "border-transparent text-text-secondary hover:border-border hover:bg-surface-elevated hover:text-text-primary",
  );
}

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === href;
  if (href === "/notifications" || href === "/profile") return pathname === href;
  return pathname.startsWith(href);
}
