"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface RiskScoreGaugeProps {
  score: number;
  className?: string;
  animated?: boolean;
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
  if (score >= 80) return "var(--color-success)";
  if (score >= 60) return "var(--color-warning)";
  if (score >= 40) return "var(--color-severity-high)";
  return "var(--color-danger)";
}

export function RiskScoreGauge({ score, className, animated = true }: RiskScoreGaugeProps) {
  const [displayScore, setDisplayScore] = useState(0);
  const clampedScore = Math.min(100, Math.max(0, score));
  const { label, textClass, bgClass } = getScoreLabel(clampedScore);
  const arcColor = getArcColor(clampedScore);

  // Animate the score on mount or when score changes
  useEffect(() => {
    if (!animated) {
      setDisplayScore(clampedScore);
      return;
    }

    const duration = 800;
    const startTime = Date.now();
    const startScore = displayScore;
    let frameId = 0;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function (ease-out cubic)
      const easeOut = 1 - Math.pow(1 - progress, 3);

      const currentScore = Math.round(startScore + (clampedScore - startScore) * easeOut);
      setDisplayScore(currentScore);

      if (progress < 1) {
        frameId = requestAnimationFrame(animate);
      }
    };

    frameId = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(frameId);
  }, [animated, clampedScore, displayScore]);

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

  // Calculate arc paths based on animated display score
  const foregroundAngleDeg = 180 - (displayScore / 100) * 180;
  const foregroundEndX = cx + r * Math.cos(toRad(foregroundAngleDeg));
  const foregroundEndY = cy + r * Math.sin(toRad(foregroundAngleDeg));
  const foregroundArcFlag = displayScore > 50 ? 1 : 0;
  const foregroundPath = `M ${bgStartX} ${bgStartY} A ${r} ${r} 0 ${foregroundArcFlag} 1 ${foregroundEndX} ${foregroundEndY}`;

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
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={arcColor} stopOpacity="0.6" />
              <stop offset="100%" stopColor={arcColor} stopOpacity="1" />
            </linearGradient>
          </defs>
          
          {/* Background arc */}
          <path
            d={bgPath}
            fill="none"
            stroke="var(--color-border)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          
          {/* Score arc with gradient */}
          {displayScore > 0 && (
            <path
              d={foregroundPath}
              fill="none"
              stroke="url(#gaugeGradient)"
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              className="transition-all duration-75"
            />
          )}
          
          {/* Decorative tick marks */}
          {[0, 25, 50, 75, 100].map((tick) => {
            const angle = 180 - (tick / 100) * 180;
            const tickR = r - strokeWidth / 2 - 4;
            const x1 = cx + (tickR - 4) * Math.cos(toRad(angle));
            const y1 = cy + (tickR - 4) * Math.sin(toRad(angle));
            const x2 = cx + tickR * Math.cos(toRad(angle));
            const y2 = cy + tickR * Math.sin(toRad(angle));
            
            return (
              <line
                key={tick}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="var(--color-border-strong)"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            );
          })}
          
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
            className="transition-all duration-75"
          >
            {displayScore}
          </text>
        </svg>
      </div>

      {/* "out of 100" label */}
      <p className="font-mono text-xs text-text-tertiary -mt-1">out of 100</p>

      {/* Pill badge with enhanced styling */}
      <span
        className={cn(
          "mt-3 inline-flex items-center rounded-full px-4 py-1 text-xs font-semibold border",
          textClass,
          bgClass,
          "border-current/20"
        )}
      >
        {label}
      </span>
    </div>
  );
}
