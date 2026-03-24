import { cn } from "@/lib/utils";

const SEVERITY_CONFIG = {
  critical: {
    label: "Critical",
    dotColor: "bg-severity-critical",
    textColor: "text-severity-critical",
    borderColor: "border-severity-critical/30",
    bgColor: "bg-severity-critical/10",
    pulse: true,
  },
  high: {
    label: "High",
    dotColor: "bg-severity-high",
    textColor: "text-severity-high",
    borderColor: "border-severity-high/30",
    bgColor: "bg-severity-high/10",
    pulse: false,
  },
  medium: {
    label: "Medium",
    dotColor: "bg-severity-medium",
    textColor: "text-severity-medium",
    borderColor: "border-severity-medium/30",
    bgColor: "bg-severity-medium/10",
    pulse: false,
  },
  low: {
    label: "Low",
    dotColor: "bg-severity-low",
    textColor: "text-severity-low",
    borderColor: "border-severity-low/30",
    bgColor: "bg-severity-low/10",
    pulse: false,
  },
  info: {
    label: "Info",
    dotColor: "bg-severity-info",
    textColor: "text-severity-info",
    borderColor: "border-severity-info/30",
    bgColor: "bg-severity-info/10",
    pulse: false,
  },
} as const;

type Severity = keyof typeof SEVERITY_CONFIG;

interface SeverityBadgeProps {
  severity: string;
  className?: string;
  showDot?: boolean;
}

export function SeverityBadge({ severity, className, showDot = true }: SeverityBadgeProps) {
  const config = SEVERITY_CONFIG[severity as Severity];
  if (!config) {
    return (
      <span className={cn("inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs font-medium font-display text-text-secondary", className)}>
        {severity}
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium font-display",
        config.borderColor,
        config.bgColor,
        config.textColor,
        className
      )}
    >
      {showDot && (
        <span className="relative flex h-2 w-2">
          {config.pulse && (
            <span className={cn("absolute inline-flex h-full w-full rounded-full opacity-75 animate-glow-pulse", config.dotColor)} />
          )}
          <span className={cn("relative inline-flex h-2 w-2 rounded-full", config.dotColor)} />
        </span>
      )}
      {config.label}
    </span>
  );
}
