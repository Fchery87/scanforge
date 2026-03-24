"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
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

interface Finding {
  id: string;
  title: string;
  severity: string;
  category: string;
  status: string;
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
    <Table className={className}>
      <TableHeader>
        <TableRow className="hover:bg-transparent border-b border-border">
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
          return (
            <TableRow
              key={f.id}
              className={cn(
                "cursor-pointer transition-colors",
                selected.includes(f.id) && "bg-primary/[0.03]",
                focusedIndex === idx && "bg-surface-hover ring-1 ring-primary/20"
              )}
            >
              <TableCell>
                <Checkbox
                  checked={selected.includes(f.id)}
                  onCheckedChange={() => onToggleSelect(f.id)}
                  aria-label={`Select finding`}
                />
              </TableCell>
              <TableCell>
                <SeverityBadge severity={f.severity} />
              </TableCell>
              <TableCell>
                <button
                  onClick={() => onSelectFinding(f.id)}
                  className="text-left text-sm text-text-primary hover:text-primary transition-colors font-medium truncate max-w-[300px] block"
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
  );
}
