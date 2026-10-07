"use client";

import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/scanforge/status-badge";

interface ScanSummaryCardsProps {
  status: string;
  branch: string;
  duration: string;
  findingCount: number;
  stale?: boolean;
  className?: string;
}

export function ScanSummaryCards({ status, branch, duration, findingCount, stale = false, className }: ScanSummaryCardsProps) {
  const cards = [
    { label: "Status", value: <StatusBadge status={stale ? "failed" : status} /> },
    { label: "Branch", value: <span className="text-sm text-text-primary">{branch}</span> },
    { label: "Duration", value: <span className="text-sm text-text-primary">{duration}</span> },
    { label: "Findings", value: <span className={`font-mono text-[1.7rem] leading-none ${findingCount > 0 ? "text-primary" : "text-text-primary"}`}>{findingCount}</span> },
  ];

  return (
    <div className={cn("grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-4", className)}>
      {cards.map((card) => (
        <div key={card.label} className="bg-background px-4 py-4">
          <p className="text-xs text-text-tertiary">{card.label}</p>
          <div className="mt-1">{card.value}</div>
        </div>
      ))}
    </div>
  );
}
