"use client";

import { cn } from "@/lib/utils";

interface EnhancedCardProps {
  children: React.ReactNode;
  className?: string;
  interactive?: boolean;
  variant?: "default" | "elevated" | "outlined";
  onClick?: () => void;
}

export function EnhancedCard({
  children,
  className,
  interactive = true,
  variant = "default",
  onClick,
}: EnhancedCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "relative rounded-xl border overflow-hidden",
        "transition-all duration-300 ease-out",
        "bg-surface",
        variant === "default" && "border-border shadow-sm",
        variant === "elevated" && [
          "border-border shadow-md",
          "shadow-primary/5"
        ],
        variant === "outlined" && [
          "border-primary/20 bg-transparent",
          "shadow-none"
        ],
        interactive && [
          "cursor-pointer",
          "hover:shadow-lg hover:shadow-primary/10",
          "hover:-translate-y-0.5",
          "hover:border-primary/30",
          "group"
        ],
        className
      )}
    >
      {/* Decorative corner accents */}
      {interactive && (
        <>
          <div className="absolute top-0 left-0 w-6 h-6 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
            <div className="absolute top-2 left-2 w-3 h-3 border-t border-l border-primary/40" />
          </div>
          <div className="absolute bottom-0 right-0 w-6 h-6 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
            <div className="absolute bottom-2 right-2 w-3 h-3 border-b border-r border-primary/40" />
          </div>
        </>
      )}

      {/* Content */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

// Shimmer loading card for skeleton states
interface ShimmerCardProps {
  className?: string;
}

export function ShimmerCard({ className }: ShimmerCardProps) {
  return (
    <div
      className={cn(
        "relative rounded-xl border border-border bg-surface p-6 overflow-hidden",
        className
      )}
    >
      {/* Shimmer effect */}
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent" />
      
      {/* Skeleton content */}
      <div className="space-y-4">
        <div className="h-4 w-1/3 bg-border rounded animate-pulse" />
        <div className="h-8 w-1/2 bg-border rounded animate-pulse" />
        <div className="h-3 w-full bg-border rounded animate-pulse" />
        <div className="h-3 w-3/4 bg-border rounded animate-pulse" />
      </div>
    </div>
  );
}

// Grid of shimmer cards
interface ShimmerGridProps {
  count?: number;
  className?: string;
}

export function ShimmerGrid({ count = 3, className }: ShimmerGridProps) {
  return (
    <div className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <ShimmerCard key={i} />
      ))}
    </div>
  );
}
