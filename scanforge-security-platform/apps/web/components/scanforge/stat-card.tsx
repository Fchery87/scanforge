import { LucideIcon, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: LucideIcon;
  value: string | number;
  label: string;
  trend?: {
    value: number;
    direction: "up" | "down";
  };
  variant?: "default" | "success" | "warning" | "danger" | "primary";
  className?: string;
}

const VARIANT_STYLES = {
  default: {
    iconBg: "bg-surface-elevated/60",
    iconColor: "text-text-secondary",
    accentColor: "",
  },
  primary: {
    iconBg: "bg-primary/10",
    iconColor: "text-primary",
    accentColor: "text-primary",
  },
  success: {
    iconBg: "bg-success/10",
    iconColor: "text-success",
    accentColor: "text-success",
  },
  warning: {
    iconBg: "bg-warning/10",
    iconColor: "text-warning",
    accentColor: "text-warning",
  },
  danger: {
    iconBg: "bg-danger/10",
    iconColor: "text-danger",
    accentColor: "text-danger",
  },
};

export function StatCard({ icon: Icon, value, label, trend, variant = "default", className }: StatCardProps) {
  const styles = VARIANT_STYLES[variant];

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-[12px] border border-border bg-surface p-5 transition-all duration-[var(--duration-base)] ease-[var(--ease-out-expo)] hover:border-border-strong hover:bg-surface-elevated",
        className
      )}
    >
      <div className={cn(
        "absolute inset-x-5 top-0 h-px opacity-100",
        variant === "primary" && "bg-gradient-to-r from-transparent via-primary/40 to-transparent",
        variant === "success" && "bg-gradient-to-r from-transparent via-success/40 to-transparent",
        variant === "warning" && "bg-gradient-to-r from-transparent via-warning/40 to-transparent",
        variant === "danger" && "bg-gradient-to-r from-transparent via-danger/40 to-transparent",
        variant === "default" && "bg-gradient-to-r from-transparent via-border-strong to-transparent",
      )} />

      <div className={cn("flex h-11 w-11 items-center justify-center rounded-[10px] border border-border/60", styles.iconBg)}>
        <Icon className={cn("h-5 w-5", styles.iconColor)} strokeWidth={1.75} />
      </div>
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className={cn("font-display text-[2rem] font-semibold leading-none tracking-[-0.03em]", styles.accentColor)}>
            {value}
          </span>
          {trend && (
            <span className={cn(
              "flex items-center gap-0.5 font-mono text-[11px] uppercase tracking-[0.1em]",
              trend.direction === "up" ? "text-success" : "text-danger"
            )}>
              {trend.direction === "up" ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {trend.value}%
            </span>
          )}
        </div>
        <span className="mt-1 block font-mono text-[11px] uppercase tracking-[0.14em] text-text-tertiary">{label}</span>
      </div>
    </div>
  );
}
