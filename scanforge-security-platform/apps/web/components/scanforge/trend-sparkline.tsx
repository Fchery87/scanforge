"use client";

import { cn } from "@/lib/utils";

interface TrendSparklineProps {
  data: number[];
  trend?: "up" | "down" | "neutral";
  width?: number;
  height?: number;
  className?: string;
  showArea?: boolean;
}

const TREND_COLORS = {
  up: "#2D5A3D", // Success green
  down: "#8B0000", // Danger red
  neutral: "#B8860B", // Primary gold
};

export function TrendSparkline({
  data,
  trend = "neutral",
  width = 60,
  height = 24,
  className,
  showArea = true,
}: TrendSparklineProps) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  // Normalize data to fit within height
  const normalizedData = data.map((value) => {
    return height - ((value - min) / range) * (height - 4) - 2;
  });

  // Generate path
  const stepX = width / (data.length - 1);
  let pathD = `M 0 ${normalizedData[0]}`;

  normalizedData.slice(1).forEach((y, i) => {
    const x = (i + 1) * stepX;
    pathD += ` L ${x} ${y}`;
  });

  // Generate area path if showArea is true
  let areaD = "";
  if (showArea) {
    areaD = `${pathD} L ${width} ${height} L 0 ${height} Z`;
  }

  const color = TREND_COLORS[trend];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
    >
      <defs>
        <linearGradient id={`sparkline-gradient-${trend}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>

      {showArea && (
        <path
          d={areaD}
          fill={`url(#sparkline-gradient-${trend})`}
          className="transition-all duration-500"
        />
      )}

      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="transition-all duration-500"
      />

      {/* End point dot */}
      <circle
        cx={width}
        cy={normalizedData[normalizedData.length - 1]}
        r="2"
        fill={color}
        className="transition-all duration-500"
      />
    </svg>
  );
}

// Mini sparkline for inline use (e.g., in tables)
interface MiniSparklineProps {
  data: number[];
  trend: "up" | "down" | "neutral";
  className?: string;
}

export function MiniSparkline({ data, trend, className }: MiniSparklineProps) {
  return (
    <TrendSparkline
      data={data}
      trend={trend}
      width={40}
      height={16}
      showArea={false}
      className={className}
    />
  );
}
