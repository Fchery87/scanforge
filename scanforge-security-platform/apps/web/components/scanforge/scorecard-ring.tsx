import { cn } from "@/lib/utils";

interface ScorecardRingProps {
  grade: string;
  overallScore?: number;
  className?: string;
}

const GRADE_COLORS: Record<string, string> = {
  A: "text-success",
  B: "text-primary",
  C: "text-warning",
  D: "text-severity-high",
  F: "text-danger",
};

const GRADE_STROKE: Record<string, string> = {
  A: "stroke-success",
  B: "stroke-primary",
  C: "stroke-warning",
  D: "stroke-severity-high",
  F: "stroke-danger",
};

export function ScorecardRing({ grade, overallScore, className }: ScorecardRingProps) {
  const firstLetter = grade?.[0] ?? "F";
  const score = overallScore ?? 0;
  const circumference = 2 * Math.PI * 30;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative h-20 w-20">
        <svg className="h-20 w-20 -rotate-90" viewBox="0 0 68 68">
          <circle
            cx="34"
            cy="34"
            r="30"
            fill="none"
            stroke="hsl(220 15% 18%)"
            strokeWidth="4"
          />
          <circle
            cx="34"
            cy="34"
            r="30"
            fill="none"
            strokeWidth="4"
            strokeLinecap="round"
            className={cn("transition-all duration-1000 ease-out", GRADE_STROKE[firstLetter] ?? "stroke-primary")}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-2xl font-bold font-display leading-none", GRADE_COLORS[firstLetter] ?? "text-primary")}>
            {grade}
          </span>
        </div>
      </div>
    </div>
  );
}
