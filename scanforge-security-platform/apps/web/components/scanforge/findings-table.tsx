"use client";

import { useState } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown, Eye, Check, Archive } from "lucide-react";
import { cn } from "@/lib/utils";
import { SeverityBadge } from "@/components/scanforge/severity-badge";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Finding {
  id: string;
  title: string;
  severity: string;
  category: string;
  status: string;
  assignee_name?: string | null;
  due_date?: string | null;
  repository_id?: string;
  first_seen_at: string;
}

interface FindingsTableProps {
  findings: Finding[];
  selected: string[];
  onToggleSelect: (id: string) => void;
  onToggleAll: () => void;
  onSelectFinding: (id: string) => void;
  sortBy: string;
  sortDir: "asc" | "desc";
  onSort: (col: string) => void;
  focusedIndex: number;
  className?: string;
}

function findingAge(firstSeenAt: string): { label: string; color: string } {
  const days = Math.floor((Date.now() - new Date(firstSeenAt).getTime()) / 86400000);
  if (days <= 7) return { label: `${days}d`, color: "text-success" };
  if (days <= 30) return { label: `${days}d`, color: "text-severity-high" };
  if (days <= 90) return { label: `${days}d`, color: "text-warning" };
  return { label: `${days}d`, color: "text-danger" };
}

function SortIcon({ col, sortBy, sortDir }: { col: string; sortBy: string; sortDir: string }) {
  if (sortBy !== col) return <ArrowUpDown className="h-3 w-3 text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />;
  return sortDir === "asc"
    ? <ArrowUp className="h-3 w-3 text-primary" />
    : <ArrowDown className="h-3 w-3 text-primary" />;
}

export function FindingsTable({
  findings,
  selected,
  onToggleSelect,
  onToggleAll,
  onSelectFinding,
  sortBy,
  sortDir,
  onSort,
  focusedIndex,
  className,
}: FindingsTableProps) {
  const allSelected = findings.length > 0 && selected.length === findings.length;

  return (
    <TooltipProvider delayDuration={200}>
    <Table className={cn("relative", className)}>
      <TableHeader className="sticky top-0 z-10 bg-surface shadow-sm">
        <TableRow className="hover:bg-transparent border-b border-border bg-surface">
          <TableHead className="w-10">
            <Checkbox
              checked={allSelected}
              onCheckedChange={onToggleAll}
              aria-label="Select all"
            />
          </TableHead>
          <TableHead className="cursor-pointer group" onClick={() => onSort("severity")}>
            <span className="inline-flex items-center gap-1">
              Severity <SortIcon col="severity" sortBy={sortBy} sortDir={sortDir} />
            </span>
          </TableHead>
          <TableHead className="min-w-[250px]">Title</TableHead>
          <TableHead className="cursor-pointer group" onClick={() => onSort("category")}>
            <span className="inline-flex items-center gap-1">
              Category <SortIcon col="category" sortBy={sortBy} sortDir={sortDir} />
            </span>
          </TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Owner</TableHead>
          <TableHead>Due</TableHead>
          <TableHead>Repository</TableHead>
          <TableHead className="cursor-pointer group" onClick={() => onSort("first_seen_at")}>
            <span className="inline-flex items-center gap-1">
              First Seen <SortIcon col="first_seen_at" sortBy={sortBy} sortDir={sortDir} />
            </span>
          </TableHead>
          <TableHead>Age</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {findings.map((f, idx) => {
          const age = findingAge(f.first_seen_at);
          const isSelected = selected.includes(f.id);
          const isFocused = focusedIndex === idx;
          
          return (
            <TableRow
              key={f.id}
              className={cn(
                "group cursor-pointer transition-all duration-200 relative",
                "hover:bg-primary/[0.04] hover:shadow-sm",
                isSelected && "bg-primary/[0.06]",
                isFocused && [
                  "bg-surface-hover",
                  "ring-1 ring-inset ring-primary/30",
                  "shadow-sm"
                ]
              )}
            >
              {/* Hover action bar */}
              <div className="absolute right-4 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-all duration-200 flex items-center gap-1 bg-surface/90 backdrop-blur-sm rounded-lg p-1 shadow-sm border border-border z-10">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectFinding(f.id);
                      }}
                      className="p-1.5 hover:bg-surface-hover rounded-md transition-colors"
                    >
                      <Eye className="h-3.5 w-3.5 text-text-tertiary hover:text-primary" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top">View details</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleSelect(f.id);
                      }}
                      className="p-1.5 hover:bg-surface-hover rounded-md transition-colors"
                    >
                      <Check className="h-3.5 w-3.5 text-text-tertiary hover:text-success" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top">Select</TooltipContent>
                </Tooltip>
              </div>

              <TableCell className="w-10">
                <Checkbox
                  checked={isSelected}
                  onCheckedChange={() => onToggleSelect(f.id)}
                  aria-label={`Select finding`}
                />
              </TableCell>
              <TableCell>
                <SeverityBadge severity={f.severity} />
              </TableCell>
              <TableCell className="min-w-[250px]">
                <button
                  onClick={() => onSelectFinding(f.id)}
                  className="text-left text-sm text-text-primary hover:text-primary transition-colors font-medium truncate max-w-[280px] block"
                >
                  {f.title}
                </button>
              </TableCell>
              <TableCell>
                <span className="text-xs text-text-secondary capitalize">
                  {f.category.replace(/_/g, " ")}
                </span>
              </TableCell>
              <TableCell>
                <StatusBadge status={f.status} showIcon={false} />
              </TableCell>
              <TableCell>
                <span className="text-xs text-text-secondary">
                  {f.assignee_name || "Unassigned"}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-xs text-text-tertiary">
                  {f.due_date ? new Date(f.due_date).toLocaleDateString() : "No date"}
                </span>
              </TableCell>
              <TableCell>
                <span className="font-mono text-xs text-text-tertiary">
                  {f.repository_id?.slice(0, 8)}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-xs text-text-tertiary">
                  {new Date(f.first_seen_at).toLocaleDateString()}
                </span>
              </TableCell>
              <TableCell>
                <span className={cn("text-xs font-medium font-mono", age.color)}>
                  {age.label}
                </span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
    </TooltipProvider>
  );
}
