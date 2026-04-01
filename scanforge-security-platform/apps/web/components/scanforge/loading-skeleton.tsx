import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

// Enhanced shimmer wrapper
function ShimmerWrapper({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("relative overflow-hidden", className)}>
      {children}
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/8 to-transparent pointer-events-none" />
    </div>
  );
}

export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <ShimmerWrapper key={i} className="rounded-xl">
          <div className="flex items-center gap-4 rounded-[12px] border border-border bg-surface p-5">
            <Skeleton className="h-10 w-10 rounded-lg shrink-0" />
            <div className="flex-1 space-y-2 min-w-0">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        </ShimmerWrapper>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <ShimmerWrapper className="rounded-xl">
      <div className="rounded-[12px] border border-border bg-surface overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-border bg-surface sticky top-0 z-10">
          <Skeleton className="h-4 w-4 shrink-0" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-3 flex-1" />
          ))}
        </div>
        {/* Rows */}
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-border/50">
            <Skeleton className="h-4 w-4 shrink-0" />
            <Skeleton className="h-5 w-16 rounded-full shrink-0" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-3 w-20 shrink-0" />
            <Skeleton className="h-3 w-16 shrink-0" />
          </div>
        ))}
      </div>
    </ShimmerWrapper>
  );
}

export function SkeletonStats({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <ShimmerWrapper key={i} className="rounded-xl">
          <div className="rounded-[12px] border border-border bg-surface p-5">
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-lg shrink-0" />
              <div className="flex-1 space-y-1.5">
                <Skeleton className="h-6 w-12" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
          </div>
        </ShimmerWrapper>
      ))}
    </div>
  );
}

export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <ShimmerWrapper key={i} className="rounded-lg">
          <div className="flex items-center gap-3 rounded-[10px] border border-border bg-surface p-4">
            <Skeleton className="h-8 w-8 rounded-full shrink-0" />
            <div className="flex-1 space-y-1.5 min-w-0">
              <Skeleton className="h-3 w-48 max-w-full" />
              <Skeleton className="h-2.5 w-32 max-w-full" />
            </div>
            <Skeleton className="h-3 w-16 shrink-0" />
          </div>
        </ShimmerWrapper>
      ))}
    </div>
  );
}
