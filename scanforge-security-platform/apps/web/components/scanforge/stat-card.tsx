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
        "group relative flex items-center gap-4 rounded-xl border border-border bg-surface/70 backdrop-blur-sm p-5 transition-all duration-300 hover:border-border-strong hover:glow-wire",
        className
      )}
    >
      {/* Accent line top */}
      <div className={cn(
        "absolute top-0 left-[15%] right-[15%] h-[1px] opacity-0 group-hover:opacity-100 transition-opacity duration-300",
        variant === "primary" && "bg-gradient-to-r from-transparent via-primary/40 to-transparent",
        variant === "success" && "bg-gradient-to-r from-transparent via-success/40 to-transparent",
        variant === "warning" && "bg-gradient-to-r from-transparent via-warning/40 to-transparent",
        variant === "danger" && "bg-gradient-to-r from-transparent via-danger/40 to-transparent",
        variant === "default" && "bg-gradient-to-r from-transparent via-border-strong to-transparent",
      )} />

      <div className={cn("flex h-11 w-11 items-center justify-center rounded-lg", styles.iconBg)}>
        <Icon className={cn("h-5 w-5", styles.iconColor)} strokeWidth={1.75} />
      </div>
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className={cn("text-2xl font-bold font-display tracking-tight", styles.accentColor)}>
            {value}
          </span>
          {trend && (
            <span className={cn(
              "flex items-center gap-0.5 text-xs font-medium",
              trend.direction === "up" ? "text-success" : "text-danger"
            )}>
              {trend.direction === "up" ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {trend.value}%
            </span>
          )}
        </div>
        <span className="text-xs text-text-tertiary font-medium">{label}</span>
      </div>
    </div>
  );
}
