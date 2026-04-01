"use client";

import Link from "next/link";
import { ChevronLeft, ChevronRight, Menu, Bell } from "lucide-react";
import { UserButton } from "@neondatabase/auth/react";

import { cn } from "@/lib/utils";

import { Breadcrumb } from "./breadcrumb";
import { CommandPalette } from "./command-palette";
import { KeyboardShortcutsModal } from "./keyboard-shortcuts-modal";

interface TopBarProps {
  isMobile: boolean;
  sidebarOpen: boolean;
  unreadCount: number;
  onToggleSidebar: () => void;
}

export function TopBar({
  isMobile,
  sidebarOpen,
  unreadCount,
  onToggleSidebar,
}: TopBarProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/88 backdrop-blur-xl">
      <div className="flex h-[76px] items-center gap-3 px-4 md:px-6 lg:px-8">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-border bg-surface text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          aria-label="Toggle sidebar"
        >
          {isMobile ? (
            <Menu className="h-4 w-4" />
          ) : sidebarOpen ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          <Breadcrumb className="hidden md:flex" />
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden lg:block">
            <CommandPalette />
          </div>
          <KeyboardShortcutsModal />
          <Link
            href="/notifications"
            className="relative flex h-11 w-11 items-center justify-center rounded-[10px] border border-border bg-surface text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            aria-label="Notifications"
          >
            <Bell className="h-[18px] w-[18px]" />
            {unreadCount > 0 ? (
              <span
                className={cn(
                  "absolute -right-1 -top-1 flex min-w-[17px] items-center justify-center rounded-full px-1 text-[9px] font-semibold text-background",
                  "bg-primary"
                )}
              >
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            ) : null}
          </Link>
          <div className="hidden md:block">
            <UserButton size="icon" />
          </div>
        </div>
      </div>
    </header>
  );
}
