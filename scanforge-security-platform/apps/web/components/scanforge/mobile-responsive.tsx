"use client";

import { useState } from "react";
import { X, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface MobileFilterSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export function MobileFilterSheet({
  isOpen,
  onClose,
  title = "Filters",
  children,
}: MobileFilterSheetProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 animate-fade-in"
        onClick={onClose}
      />
      
      {/* Sheet */}
      <div className="fixed bottom-0 left-0 right-0 z-50 bg-surface rounded-t-2xl shadow-2xl animate-slide-up max-h-[80vh] overflow-hidden">
        {/* Handle bar */}
        <div className="flex items-center justify-center pt-3 pb-2">
          <div className="w-12 h-1 bg-border rounded-full" />
        </div>
        
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="text-lg font-semibold font-display text-text-primary">{title}</h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-surface-hover rounded-lg transition-colors touch-target"
          >
            <X className="h-5 w-5 text-text-secondary" />
          </button>
        </div>
        
        {/* Content */}
        <div className="overflow-y-auto p-4 max-h-[calc(80vh-80px)]">
          {children}
        </div>
      </div>
    </>
  );
}

// Trigger button for mobile filters
interface MobileFilterTriggerProps {
  activeFiltersCount?: number;
  onClick: () => void;
}

export function MobileFilterTrigger({ activeFiltersCount = 0, onClick }: MobileFilterTriggerProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
      className="lg:hidden touch-target"
    >
      <SlidersHorizontal className="h-4 w-4 mr-2" />
      Filters
      {activeFiltersCount > 0 && (
        <span className="ml-2 px-1.5 py-0.5 bg-primary text-white text-xs rounded-full">
          {activeFiltersCount}
        </span>
      )}
    </Button>
  );
}

// Responsive table wrapper with scroll indicators
interface ResponsiveTableProps {
  children: React.ReactNode;
  className?: string;
  minWidth?: string;
}

export function ResponsiveTable({
  children,
  className,
  minWidth = "800px",
}: ResponsiveTableProps) {
  return (
    <div className={cn("relative", className)}>
      {/* Left fade indicator */}
      <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-surface to-transparent pointer-events-none z-10 opacity-0 md:opacity-100" />
      
      {/* Right fade indicator */}
      <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-surface to-transparent pointer-events-none z-10 opacity-0 md:opacity-100" />
      
      {/* Scrollable container */}
      <div className="overflow-x-auto -mx-4 px-4 pb-2 scrollbar-thin">
        <div style={{ minWidth }}>{children}</div>
      </div>
    </div>
  );
}
