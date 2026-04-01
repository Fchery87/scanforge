import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn("card-serif animate-fade-up px-6 py-16 text-center", className)}>
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[14px] border border-border bg-surface-elevated mb-5">
        <Icon className="h-7 w-7 text-text-tertiary" strokeWidth={1.5} />
      </div>
      <p className="section-title mb-3">No Results</p>
      <h3 className="text-[1.35rem] font-semibold font-display text-text-primary mb-2">{title}</h3>
      <p className="mx-auto max-w-[34rem] text-sm leading-relaxed text-text-secondary mb-6">{description}</p>
      {action}
    </div>
  );
}
