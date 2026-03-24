"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { api } from "@/lib/api";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [orgs, setOrgs] = useState<any[]>([]);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  useEffect(() => {
    if (open && orgs.length === 0) {
      api.organizations.list(0, 20).then((res) => {
        setOrgs(res.items ?? []);
      }).catch(() => {});
    }
  }, [open, orgs.length]);

  const navigate = useCallback((href: string) => {
    setOpen(false);
    router.push(href);
  }, [router]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-text-tertiary hover:bg-surface-hover hover:text-text-secondary transition-colors"
      >
        <span>Navigate...</span>
        <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-0.5 rounded border border-border bg-surface-elevated px-1.5 font-mono text-[10px] font-medium text-text-tertiary">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Search organizations, projects, findings..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Navigation">
            <CommandItem onSelect={() => navigate("/dashboard")}>
              Dashboard
            </CommandItem>
            <CommandItem onSelect={() => navigate("/notifications")}>
              Notifications
            </CommandItem>
            <CommandItem onSelect={() => navigate("/onboarding")}>
              Onboarding
            </CommandItem>
            <CommandItem onSelect={() => navigate("/profile")}>
              Profile
            </CommandItem>
          </CommandGroup>
          {orgs.length > 0 && (
            <>
              <CommandSeparator />
              <CommandGroup heading="Organizations">
                {orgs.map((org) => (
                  <CommandItem key={org.id} onSelect={() => navigate(`/dashboard/${org.id}`)}>
                    {org.name}
                    <CommandShortcut className="font-mono text-[10px]">{org.slug}</CommandShortcut>
                  </CommandItem>
                ))}
              </CommandGroup>
            </>
          )}
        </CommandList>
      </CommandDialog>
    </>
  );
}
