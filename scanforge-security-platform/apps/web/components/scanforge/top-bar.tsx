"use client";

import Link from "next/link";
import { Bell, Menu, PanelLeft } from "lucide-react";
import { UserButton } from "@neondatabase/auth/react";

import { Breadcrumb } from "./breadcrumb";
import { CommandPalette } from "./command-palette";

interface TopBarProps {
  isMobile: boolean;
  sidebarOpen: boolean;
  unreadCount: number;
  onToggleSidebar: () => void;
}

export function TopBar({ isMobile, unreadCount, onToggleSidebar }: TopBarProps) {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-2 border-b border-border bg-background px-5 md:px-8">
      <button
        type="button"
        onClick={onToggleSidebar}
        className="flex h-9 w-9 items-center justify-center rounded-md text-text-secondary hover-fine:text-text-primary"
        aria-label="Toggle sidebar"
      >
        {isMobile ? <Menu className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
      </button>
      <div className="min-w-0 flex-1">
        <Breadcrumb className="hidden md:flex" />
      </div>
      <div className="hidden lg:block">
        <CommandPalette />
      </div>
      <Link
        href="/notifications"
        className="relative flex h-9 w-9 items-center justify-center rounded-md text-text-secondary hover-fine:text-text-primary"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 ? (
          <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-primary" />
        ) : null}
      </Link>
      <div className="hidden md:block">
        <UserButton size="icon" />
      </div>
    </header>
  );
}
