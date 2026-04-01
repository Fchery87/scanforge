import { AlertOctagon, AlertTriangle, AlertCircle, Info, Shield } from "lucide-react";
import { getSeverityMeta } from "@/lib/scanforge-ui";
import { cn } from "@/lib/utils";

const SEVERITY_CONFIG = {
  critical: {
    label: "Critical",
    icon: AlertOctagon,
    dotColor: "bg-severity-critical",
    textColor: "text-severity-critical",
    borderColor: "border-severity-critical/40",
    bgColor: "bg-severity-critical/15",
    pulse: true,
    glow: "shadow-[0_0_12px_rgba(139,0,0,0.25)]",
  },
  high: {
    label: "High",
    icon: AlertTriangle,
    dotColor: "bg-severity-high",
    textColor: "text-severity-high",
    borderColor: "border-severity-high/40",
    bgColor: "bg-severity-high/15",
    pulse: false,
    glow: "",
  },
  medium: {
    label: "Medium",
    icon: AlertCircle,
    dotColor: "bg-severity-medium",
    textColor: "text-severity-medium",
    borderColor: "border-severity-medium/40",
    bgColor: "bg-severity-medium/15",
    pulse: false,
    glow: "",
  },
  low: {
    label: "Low",
    icon: Shield,
    dotColor: "bg-severity-low",
    textColor: "text-severity-low",
    borderColor: "border-severity-low/40",
    bgColor: "bg-severity-low/15",
    pulse: false,
    glow: "",
  },
  info: {
    label: "Info",
    icon: Info,
    dotColor: "bg-severity-info",
    textColor: "text-severity-info",
    borderColor: "border-severity-info/40",
    bgColor: "bg-severity-info/15",
    pulse: false,
    glow: "",
  },
} as const;

type Severity = keyof typeof SEVERITY_CONFIG;

interface SeverityBadgeProps {
  severity: string;
  className?: string;
  showDot?: boolean;
  showIcon?: boolean;
  size?: "sm" | "md";
}

export function SeverityBadge({ 
  severity, 
  className, 
  showDot = true, 
  showIcon = false,
  size = "sm"
}: SeverityBadgeProps) {
  const meta = getSeverityMeta(severity);
  const config = SEVERITY_CONFIG[meta.key as Severity];
  if (!config) {
    return (
      <span className={cn(
        "inline-flex items-center gap-1.5 rounded-[6px] border border-border bg-surface-elevated font-mono font-medium uppercase tracking-[0.12em] text-text-secondary",
        size === "sm" ? "px-2.5 py-1 text-[11px]" : "px-3 py-1.5 text-xs",
        className
      )}>
        {meta.label}
      </span>
    );
  }

  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[6px] border font-mono font-medium uppercase tracking-[0.12em] transition-all duration-200",
        size === "sm" ? "px-2.5 py-1 text-[11px]" : "px-3 py-1.5 text-xs",
        config.borderColor,
        config.bgColor,
        config.textColor,
        config.glow,
        className
      )}
    >
      {showIcon && Icon && (
        <Icon className={cn(
          "shrink-0",
          size === "sm" ? "h-3 w-3" : "h-4 w-4"
        )} />
      )}
      
      {showDot && !showIcon && (
        <span className="relative flex h-2 w-2">
          {config.pulse && (
            <span className={cn("absolute inline-flex h-full w-full rounded-full opacity-75 animate-glow-pulse", config.dotColor)} />
          )}
          <span className={cn("relative inline-flex h-2 w-2 rounded-full", config.dotColor)} />
        </span>
      )}
      
      {meta.label}
    </span>
  );
}
