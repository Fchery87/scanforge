"use client";

import { useState } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { FindingsFilters } from "@/lib/findings/filter-state";
import { buildSavedViewPayload, hasActiveFilters } from "@/lib/findings/filter-state";

interface FindingsSavedViewBarProps {
  filters: FindingsFilters;
  onSaveView: (payload: { name: string; filters: Record<string, string> }) => void;
  savedViews?: Array<{ name: string; filters: Record<string, string> }>;
  onApplyView?: (filters: Record<string, string>) => void;
  className?: string;
}

export function FindingsSavedViewBar({
  filters,
  onSaveView,
  savedViews = [],
  onApplyView,
  className,
}: FindingsSavedViewBarProps) {
  const [saving, setSaving] = useState(false);
  const [viewName, setViewName] = useState("");

  const isActive = hasActiveFilters(filters);

  const handleSave = () => {
    if (!viewName.trim() || !isActive) return;
    setSaving(true);
    onSaveView(buildSavedViewPayload(filters, viewName.trim()));
    setViewName("");
    setSaving(false);
  };

  if (!isActive && savedViews.length === 0) return null;

  return (
    <div className={cn("flex items-center gap-2 flex-wrap py-2", className)}>
      {savedViews.length > 0 && (
        <>
          <span className="text-xs text-text-tertiary">Saved:</span>
          {savedViews.map((view) => (
            <Badge
              key={view.name}
              variant="outline"
              className="cursor-pointer text-xs"
              onClick={() => onApplyView?.(view.filters)}
            >
              <BookmarkCheck className="h-3 w-3 mr-1" />
              {view.name}
            </Badge>
          ))}
        </>
      )}
      {isActive && (
        <div className="flex items-center gap-1.5 ml-auto">
          <Input
            placeholder="Save as view..."
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            className="h-8 w-40 text-xs"
          />
          <Button size="sm" variant="ghost" onClick={handleSave} disabled={saving || !viewName.trim()} className="h-8 gap-1 text-xs">
            <Bookmark className="h-3.5 w-3.5" />
            Save
          </Button>
        </div>
      )}
    </div>
  );
}
