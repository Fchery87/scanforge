import { cn } from "@/lib/utils";

interface TrendDataPoint {
  date: string;
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
  info?: number;
}

interface TrendChartProps {
  data: TrendDataPoint[];
  className?: string;
}

export function TrendChart({ data, className }: TrendChartProps) {
  if (!data || data.length === 0) return null;

  const width = 600;
  const height = 120;
  const padding = { top: 8, right: 8, bottom: 20, left: 8 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const maxVal = Math.max(
    1,
    ...data.map((d) =>
      (d.critical ?? 0) + (d.high ?? 0) + (d.medium ?? 0) + (d.low ?? 0) + (d.info ?? 0)
    )
  );

  const getX = (i: number) => padding.left + (i / (data.length - 1)) * chartWidth;
  const getY = (val: number) => padding.top + chartHeight - (val / maxVal) * chartHeight;

  function buildAreaPath(key: keyof Omit<TrendDataPoint, "date">, base: number[] = []) {
    const points = data.map((d, i) => {
      const val = (d[key] ?? 0) + (base[i] ?? 0);
      return { x: getX(i), y: getY(val) };
    });
    const basePoints = data.map((_, i) => ({
      x: getX(i),
      y: base.length > 0 ? getY(base[i]) : padding.top + chartHeight,
    }));

    let path = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const cp1x = (points[i - 1].x + points[i].x) / 2;
      path += ` C ${cp1x} ${points[i - 1].y}, ${cp1x} ${points[i].y}, ${points[i].x} ${points[i].y}`;
    }
    for (let i = basePoints.length - 1; i >= 0; i--) {
      const _cp1x = (basePoints[Math.min(i + 1, basePoints.length - 1)].x + basePoints[i].x) / 2;
      path += ` L ${basePoints[i].x} ${basePoints[i].y}`;
    }
    path += " Z";
    return path;
  }

  const totals = data.map((d) => (d.critical ?? 0) + (d.high ?? 0) + (d.medium ?? 0) + (d.low ?? 0) + (d.info ?? 0));
  const _prevTotals = totals.map((_, i) => totals.slice(0, i + 1).reduce((a, b) => a + b, 0));

  return (
    <div className={cn("rounded-xl border border-border bg-surface p-4", className)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
        <defs>
          <linearGradient id="trend-gradient-info" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#135bec" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#135bec" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="trend-gradient-low" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="trend-gradient-medium" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#eab308" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#eab308" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="trend-gradient-high" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#f97316" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#f97316" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="trend-gradient-critical" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#ef4444" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {[0.25, 0.5, 0.75].map((pct) => (
          <line
            key={pct}
            x1={padding.left}
            y1={padding.top + chartHeight * pct}
            x2={padding.left + chartWidth}
            y2={padding.top + chartHeight * pct}
            stroke="var(--color-border)"
            strokeWidth="0.5"
            strokeDasharray="4 4"
          />
        ))}

        {/* Stacked areas */}
        <path d={buildAreaPath("info")} fill="url(#trend-gradient-info)" />
        <path d={buildAreaPath("low", data.map((d) => (d.info ?? 0)))} fill="url(#trend-gradient-low)" />
        <path d={buildAreaPath("medium", data.map((d) => (d.info ?? 0) + (d.low ?? 0)))} fill="url(#trend-gradient-medium)" />
        <path d={buildAreaPath("high", data.map((d) => (d.info ?? 0) + (d.low ?? 0) + (d.medium ?? 0)))} fill="url(#trend-gradient-high)" />
        <path d={buildAreaPath("critical", data.map((d) => (d.info ?? 0) + (d.low ?? 0) + (d.medium ?? 0) + (d.high ?? 0)))} fill="url(#trend-gradient-critical)" />

        {/* Date labels */}
        {data.length > 1 && (
          <>
            <text x={padding.left} y={height - 2} fill="var(--color-text-tertiary)" fontSize="9" fontFamily="var(--font-mono)">
              {data[0].date.slice(5)}
            </text>
            <text x={padding.left + chartWidth} y={height - 2} fill="var(--color-text-tertiary)" fontSize="9" fontFamily="var(--font-mono)" textAnchor="end">
              {data[data.length - 1].date.slice(5)}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}
