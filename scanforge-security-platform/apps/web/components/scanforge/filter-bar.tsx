"use client";

import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface FilterOption {
  value: string;
  label: string;
}

interface FilterConfig {
  key: string;
  label: string;
  options: FilterOption[];
  value: string;
  onChange: (value: string) => void;
}

interface FilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters: FilterConfig[];
  onClearAll?: () => void;
  className?: string;
}

export function FilterBar({
  searchValue,
  onSearchChange,
  searchPlaceholder = "Search...",
  filters,
  onClearAll,
  className,
}: FilterBarProps) {
  const activeFilterCount = filters.filter((f) => f.value).length + (searchValue ? 1 : 0);

  return (
    <div className={cn("card-serif p-4", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary" />
          <Input
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="h-11 border-border bg-background pl-9"
          />
        </div>

        {filters.map((filter) => (
          <select
            key={filter.key}
            value={filter.value}
            onChange={(e) => filter.onChange(e.target.value)}
            className="flex h-11 rounded-[8px] border border-border bg-background px-3 py-2 text-sm text-text-primary transition-colors focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
          >
            <option value="">{filter.label}</option>
            {filter.options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ))}

        {/* Clear all */}
        {activeFilterCount > 0 && onClearAll && (
          <Button variant="ghost" size="sm" onClick={onClearAll} className="gap-1.5 self-stretch px-3">
            <X className="h-3.5 w-3.5" />
            Clear
            {activeFilterCount > 1 && (
              <Badge variant="primary" className="ml-0.5 text-[10px] px-1.5 py-0">
                {activeFilterCount}
              </Badge>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
