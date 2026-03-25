import { cn } from "@/lib/utils";

interface RiskScoreGaugeProps {
  score: number;
  className?: string;
}

function getScoreLabel(score: number): {
  label: string;
  textClass: string;
  bgClass: string;
} {
  if (score >= 80) {
    return {
      label: "Good",
      textClass: "text-success",
      bgClass: "bg-success/10",
    };
  }
  if (score >= 60) {
    return {
      label: "Moderate",
      textClass: "text-warning",
      bgClass: "bg-warning/10",
    };
  }
  if (score >= 40) {
    return {
      label: "At Risk",
      textClass: "text-severity-high",
      bgClass: "bg-severity-high/10",
    };
  }
  return {
    label: "Critical",
    textClass: "text-danger",
    bgClass: "bg-danger/10",
  };
}

function getArcColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}

export function RiskScoreGauge({ score, className }: RiskScoreGaugeProps) {
  const clampedScore = Math.min(100, Math.max(0, score));
  const { label, textClass, bgClass } = getScoreLabel(clampedScore);
  const arcColor = getArcColor(clampedScore);

  // SVG dimensions
  const cx = 100;
  const cy = 100;
  const r = 80;
  const strokeWidth = 12;

  // The arc spans 180 degrees (from 180deg to 0deg, i.e. left to right along top)
  // Start: left side (180deg), End: right side (0deg)
  const startAngleDeg = 180;
  const endAngleDeg = 0;

  const toRad = (deg: number) => (deg * Math.PI) / 180;

  // Background arc: full 180 degrees
  const bgStartX = cx + r * Math.cos(toRad(startAngleDeg));
  const bgStartY = cy + r * Math.sin(toRad(startAngleDeg));
  const bgEndX = cx + r * Math.cos(toRad(endAngleDeg));
  const bgEndY = cy + r * Math.sin(toRad(endAngleDeg));
  const bgPath = `M ${bgStartX} ${bgStartY} A ${r} ${r} 0 0 1 ${bgEndX} ${bgEndY}`;

  // Foreground arc: score/100 of 180 degrees, from left (180deg) sweeping clockwise
  const scoreAngleDeg = 180 - (clampedScore / 100) * 180;
  const fgEndX = cx + r * Math.cos(toRad(scoreAngleDeg));
  const fgEndY = cy + r * Math.sin(toRad(scoreAngleDeg));
  const largeArcFlag = clampedScore > 50 ? 1 : 0;
  const fgPath = `M ${bgStartX} ${bgStartY} A ${r} ${r} 0 ${largeArcFlag} 1 ${fgEndX} ${fgEndY}`;

  return (
    <div className={cn("flex flex-col items-center", className)}>
      <div className="relative w-[200px]">
        <svg
          viewBox="0 0 200 105"
          width="200"
          height="105"
          aria-label={`Risk score: ${clampedScore} out of 100 — ${label}`}
          role="img"
        >
          {/* Background arc */}
          <path
            d={bgPath}
            fill="none"
            stroke="var(--color-border-strong)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Score arc */}
          {clampedScore > 0 && (
            <path
              d={fgPath}
              fill="none"
              stroke={arcColor}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
            />
          )}
          {/* Score number */}
          <text
            x={cx}
            y={cy - 2}
            textAnchor="middle"
            dominantBaseline="auto"
            fontSize="36"
            fontWeight="700"
            fontFamily="var(--font-display)"
            fill="var(--color-text-primary)"
          >
            {clampedScore}
          </text>
        </svg>
      </div>

      {/* "out of 100" label */}
      <p className="font-mono text-xs text-text-tertiary -mt-1">out of 100</p>

      {/* Pill badge */}
      <span
        className={cn(
          "mt-2 inline-flex items-center rounded-full px-3 py-0.5 text-xs font-semibold",
          textClass,
          bgClass
        )}
      >
        {label}
      </span>
    </div>
  );
}
