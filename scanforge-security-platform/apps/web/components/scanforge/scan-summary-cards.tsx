"use client";

import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/scanforge/status-badge";

interface ScanSummaryCardsProps {
  status: string;
  branch: string;
  duration: string;
  findingCount: number;
  className?: string;
}

export function ScanSummaryCards({ status, branch, duration, findingCount, className }: ScanSummaryCardsProps) {
  const cards = [
    { label: "Status", value: <StatusBadge status={status} /> },
    { label: "Branch", value: <span className="text-sm text-text-primary">{branch}</span> },
    { label: "Duration", value: <span className="text-sm text-text-primary">{duration}</span> },
    { label: "Findings", value: <span className="font-display text-[1.8rem] leading-none text-text-primary">{findingCount}</span> },
  ];

  return (
    <div className={cn("grid gap-4 md:grid-cols-4", className)}>
      {cards.map((card) => (
        <div key={card.label} className="card-serif p-4">
          <p className="section-title">{card.label}</p>
          <div className="mt-3">{card.value}</div>
        </div>
      ))}
    </div>
  );
}
