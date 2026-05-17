"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const SHORTCUTS = [
  { category: "Navigation", items: [
    { keys: ["⌘", "K"], description: "Open command palette" },
    { keys: ["/"], description: "Focus search on current page" },
    { keys: ["G", "D"], description: "Go to Dashboard" },
    { keys: ["G", "N"], description: "Go to Notifications" },
  ]},
  { category: "Findings", items: [
    { keys: ["J"], description: "Next finding" },
    { keys: ["K"], description: "Previous finding" },
    { keys: ["Enter"], description: "Open selected finding" },
    { keys: ["Esc"], description: "Close finding drawer" },
    { keys: ["X"], description: "Toggle selection" },
  ]},
  { category: "General", items: [
    { keys: ["?"], description: "Show keyboard shortcuts" },
    { keys: ["N"], description: "New item (context-aware)" },
    { keys: ["Esc"], description: "Close modal / dismiss" },
  ]},
];

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="inline-flex h-6 min-w-[24px] items-center justify-center rounded-md border border-border bg-surface-elevated px-1.5 font-mono text-[11px] font-medium text-text-secondary shadow-sm">
      {children}
    </kbd>
  );
}

export function KeyboardShortcutsModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      // Don't trigger in inputs
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT") return;
      // Don't trigger if meta/ctrl is held (that's for Cmd+K)
      if (e.metaKey || e.ctrlKey) return;

      if (e.key === "?") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors text-xs font-mono font-bold"
        aria-label="Keyboard shortcuts"
      >
        ?
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Keyboard Shortcuts</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            {SHORTCUTS.map((group) => (
              <div key={group.category}>
                <h3 className="text-[10px] font-semibold text-text-tertiary uppercase tracking-widest mb-2">
                  {group.category}
                </h3>
                <div className="space-y-1">
                  {group.items.map((shortcut) => (
                    <div key={shortcut.description} className="flex items-center justify-between py-1.5">
                      <span className="text-sm text-text-secondary">{shortcut.description}</span>
                      <div className="flex items-center gap-1">
                        {shortcut.keys.map((key, i) => (
                          <span key={i} className="flex items-center gap-1">
                            {i > 0 && <span className="text-text-tertiary text-xs">then</span>}
                            <Kbd>{key}</Kbd>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
