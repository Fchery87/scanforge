"use client";

import { Loader2, AlertTriangle, Inbox, WifiOff } from "lucide-react";
import { EmptyState } from "./empty-state";

interface PageStatePanelProps {
  state: "loading" | "error" | "empty" | "ready" | "unavailable";
  message?: string;
  retry?: () => void;
  emptyIcon?: React.ReactNode;
  children?: React.ReactNode;
}

export function PageStatePanel({
  state,
  message,
  retry,
  emptyIcon: _emptyIcon,
  children,
}: PageStatePanelProps) {
  if (state === "loading") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-up">
        <Loader2 className="h-8 w-8 animate-spin text-text-tertiary mb-4" />
        <p className="text-sm text-text-secondary">Loading...</p>
      </div>
    );
  }

  if (state === "error") {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Something went wrong"
        description={message ?? "An unexpected error occurred."}
        action={
          retry && (
            <button
              onClick={retry}
              className="mt-4 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Try Again
            </button>
          )
        }
      />
    );
  }

  if (state === "empty") {
    return (
      <EmptyState
        icon={Inbox}
        title="Nothing here yet"
        description={message ?? "No data available."}
      />
    );
  }

  if (state === "unavailable") {
    return (
      <EmptyState
        icon={WifiOff}
        title="Not available"
        description={message ?? "This feature requires a connected integration."}
      />
    );
  }

  return <>{children}</>;
}
