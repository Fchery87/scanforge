import { CheckCircle, XCircle, Clock, Loader2, Pause } from "lucide-react";
import { getStatusMeta } from "@/lib/scanforge-ui";
import { cn } from "@/lib/utils";

const STATUS_CONFIG = {
  open: { label: "Open", color: "text-warning", bgColor: "bg-warning/10", borderColor: "border-warning/30", icon: Clock },
  fixed: { label: "Fixed", color: "text-success", bgColor: "bg-success/10", borderColor: "border-success/30", icon: CheckCircle },
  suppressed: { label: "Suppressed", color: "text-text-secondary", bgColor: "bg-surface-elevated", borderColor: "border-border", icon: Pause },
  accepted_risk: { label: "Accepted", color: "text-info", bgColor: "bg-info/10", borderColor: "border-info/30", icon: CheckCircle },
  duplicate: { label: "Duplicate", color: "text-text-tertiary", bgColor: "bg-surface-elevated", borderColor: "border-border", icon: XCircle },
  completed: { label: "Completed", color: "text-success", bgColor: "bg-success/10", borderColor: "border-success/30", icon: CheckCircle },
  failed: { label: "Failed", color: "text-danger", bgColor: "bg-danger/10", borderColor: "border-danger/30", icon: XCircle },
  running: { label: "Running", color: "text-primary", bgColor: "bg-primary/10", borderColor: "border-primary/30", icon: Loader2 },
  queued: { label: "Queued", color: "text-text-tertiary", bgColor: "bg-surface-elevated", borderColor: "border-border", icon: Clock },
  canceled: { label: "Canceled", color: "text-warning", bgColor: "bg-warning/10", borderColor: "border-warning/30", icon: XCircle },
} as const;

type Status = keyof typeof STATUS_CONFIG;

interface StatusBadgeProps {
  status: string;
  className?: string;
  showIcon?: boolean;
}

export function StatusBadge({ status, className, showIcon = true }: StatusBadgeProps) {
  const meta = getStatusMeta(status);
  const config = STATUS_CONFIG[meta.key as Status];
  if (!config) {
    return (
      <span className={cn("inline-flex items-center gap-1.5 rounded-[6px] border border-border bg-surface-elevated px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-text-secondary", className)}>
        {meta.label}
      </span>
    );
  }

  const Icon = config.icon;
  const isRunning = status === "running";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[6px] border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.12em]",
        config.borderColor,
        config.bgColor,
        config.color,
        className
      )}
    >
      {showIcon && (
        <Icon className={cn("h-3 w-3", isRunning && "animate-spin")} />
      )}
      {meta.label}
    </span>
  );
}
