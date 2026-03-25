import { cn } from "@/lib/utils";

interface SeverityBreakdownProps {
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
  className?: string;
}

interface SeverityRowProps {
  dot: string;
  label: string;
  count: number;
  textColor: string;
}

function SeverityRow({ dot, label, count, textColor }: SeverityRowProps) {
  return (
    <div className="flex items-center gap-2">
      <span className={cn("h-2 w-2 rounded-full shrink-0", dot)} />
      <span className="text-xs text-text-tertiary">{label}</span>
      <span className={cn("ml-auto text-xs font-bold font-mono", textColor)}>
        {count}
      </span>
    </div>
  );
}

export function SeverityBreakdown({
  critical = 0,
  high = 0,
  medium = 0,
  low = 0,
  className,
}: SeverityBreakdownProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <SeverityRow
        dot="bg-severity-critical"
        label="Crit"
        count={critical}
        textColor="text-severity-critical"
      />
      <SeverityRow
        dot="bg-severity-high"
        label="High"
        count={high}
        textColor="text-severity-high"
      />
      <SeverityRow
        dot="bg-severity-medium"
        label="Med"
        count={medium}
        textColor="text-severity-medium"
      />
      <SeverityRow
        dot="bg-severity-low"
        label="Low"
        count={low}
        textColor="text-severity-low"
      />
    </div>
  );
}
