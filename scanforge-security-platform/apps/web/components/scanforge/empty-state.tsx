import type { LucideIcon } from "lucide-react";
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
    <div className={cn("rounded-md border border-dashed border-border px-6 py-12 text-center", className)}>
      <Icon className="mx-auto mb-3 h-5 w-5 text-text-tertiary" strokeWidth={1.75} />
      <h3 className="mb-1 text-[0.95rem] font-medium text-text-primary">{title}</h3>
      <p className="mx-auto mb-5 max-w-[36rem] text-sm leading-relaxed text-text-secondary">{description}</p>
      {action}
    </div>
  );
}
