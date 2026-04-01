"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { OnboardingNextAction } from "@/lib/onboarding/next-step";

interface OnboardingNextActionsProps {
  actions: OnboardingNextAction[];
  className?: string;
}

export function OnboardingNextActions({ actions, className }: OnboardingNextActionsProps) {
  if (actions.length === 0) return null;

  return (
    <div className={cn("mt-6 space-y-3", className)}>
      <h3 className="text-sm font-medium text-text-secondary">Next Steps</h3>
      {actions.map((action) => (
        <div
          key={action.id}
          className="flex items-start gap-3 rounded-[10px] border border-border bg-background p-4"
        >
          <CheckCircle2 className="h-5 w-5 text-primary mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text-primary">{action.label}</p>
            <p className="text-xs text-text-tertiary mt-1">{action.description}</p>
          </div>
          {action.url ? (
            <Link href={action.url} className="shrink-0">
              <Button size="sm" variant={action.isPrimary ? "default" : "outline"}>
                Go <ArrowRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </Link>
          ) : (
            <Button size="sm" variant={action.isPrimary ? "default" : "outline"} disabled>
              In Progress
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
