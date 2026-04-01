"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";

interface FindingsBarChartProps {
  data: Array<{
    date: string;
    count?: number;
    critical?: number;
    high?: number;
    medium?: number;
    low?: number;
    info?: number;
  }>;
  className?: string;
}

const SEVERITY_COLORS = {
  critical: "var(--color-chart-critical)",
  high: "var(--color-chart-high)",
  medium: "var(--color-chart-medium)",
  low: "var(--color-chart-low)",
  info: "var(--color-chart-info)",
} as const;

function hasSeverityBreakdown(
  item: FindingsBarChartProps["data"][number]
): boolean {
  return (
    item.critical !== undefined ||
    item.high !== undefined ||
    item.medium !== undefined ||
    item.low !== undefined ||
    item.info !== undefined
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-lg border border-border bg-surface-elevated px-3 py-2 shadow-lg">
      <p className="mb-1 font-mono text-xs text-text-secondary">{label}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="font-mono text-xs capitalize text-text-secondary">
            {entry.name}:
          </span>
          <span className="font-mono text-xs font-bold text-text-primary">
            {entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export function FindingsBarChart({ data, className }: FindingsBarChartProps) {
  const usesSeverity = data.length > 0 && hasSeverityBreakdown(data[0]);

  const formattedData = data.map((item) => ({
    ...item,
    date: item.date.slice(5),
  }));

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface p-5",
        className
      )}
    >
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-tertiary">
        Findings Over Last 30 Days
      </p>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          data={formattedData}
          margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
        >
          <CartesianGrid
            vertical={false}
            stroke="var(--color-border)"
            strokeDasharray="4 4"
          />
          <XAxis
            dataKey="date"
            tick={{
              fill: "var(--color-text-tertiary)",
              fontSize: 10,
              fontFamily: "var(--font-mono)",
            }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{
              fill: "var(--color-text-tertiary)",
              fontSize: 10,
              fontFamily: "var(--font-mono)",
            }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: "var(--color-surface-hover)" }}
          />

          {usesSeverity ? (
            <>
              <Bar
                dataKey="info"
                name="info"
                stackId="severity"
                fill={SEVERITY_COLORS.info}
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="low"
                name="low"
                stackId="severity"
                fill={SEVERITY_COLORS.low}
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="medium"
                name="medium"
                stackId="severity"
                fill={SEVERITY_COLORS.medium}
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="high"
                name="high"
                stackId="severity"
                fill={SEVERITY_COLORS.high}
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="critical"
                name="critical"
                stackId="severity"
                fill={SEVERITY_COLORS.critical}
                radius={[2, 2, 0, 0]}
              />
            </>
          ) : (
            <Bar
              dataKey="count"
              name="findings"
              fill="#8b5cf6"
              radius={[2, 2, 0, 0]}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
