import { TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  icon: LucideIcon;
  value: string | number;
  label: string;
  trend?: { value: number; direction: "up" | "down" };
  variant?: "default" | "success" | "warning" | "danger" | "primary";
  className?: string;
}

export function StatCard({ value, label, trend, variant = "default", className }: StatCardProps) {
  return (
    <div className={cn("border-b border-border py-3", className)}>
      <p className="text-[0.75rem] text-text-tertiary">{label}</p>
      <p
        className={cn(
          "mt-1 font-mono text-[1.75rem] leading-none tracking-[-0.03em]",
          variant === "danger" || variant === "primary" ? "text-primary" : "text-text-primary"
        )}
      >
        {value}
      </p>
      {trend ? (
        <p className={cn("mt-1 flex items-center gap-1 text-xs", trend.direction === "up" ? "text-primary" : "text-success")}>
          {trend.direction === "up" ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
          {trend.value}
        </p>
      ) : null}
    </div>
  );
}
