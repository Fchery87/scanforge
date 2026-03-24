"use client";

import { CheckCircle2, Circle, ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface OnboardingStepProps {
  id: string;
  label: string;
  description: string;
  completed: boolean;
  icon: LucideIcon;
  actionUrl?: string | null;
  children?: React.ReactNode;
  className?: string;
}

export function OnboardingStepCard({
  label,
  description,
  completed,
  icon: Icon,
  actionUrl,
  children,
  className,
}: OnboardingStepProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-4 rounded-xl border border-border bg-surface p-5 transition-all duration-200",
        completed && "border-success/30 bg-success/[0.03]",
        !completed && "hover:border-border-strong",
        className
      )}
    >
      <div
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-lg flex-shrink-0 mt-0.5",
          completed ? "bg-success/10 text-success" : "bg-surface-elevated text-text-tertiary"
        )}
      >
        {completed ? <CheckCircle2 className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
      </div>

      <div className="flex-1 min-w-0">
        <h3 className={cn("text-sm font-semibold font-display", completed ? "text-success" : "text-text-primary")}>
          {label}
        </h3>
        <p className="text-xs text-text-tertiary mt-0.5">{description}</p>
        {children && <div className="mt-3">{children}</div>}
      </div>

      {completed && (
        <span className="text-[10px] font-semibold text-success bg-success/10 border border-success/30 rounded-full px-2 py-0.5 flex-shrink-0 mt-1">
          Complete
        </span>
      )}

      {actionUrl && !completed && (
        <Link href={actionUrl}>
          <Button variant="ghost" size="sm" className="gap-1">
            Go <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      )}
    </div>
  );
}
