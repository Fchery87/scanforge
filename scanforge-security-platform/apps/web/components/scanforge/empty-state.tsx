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
    <div className={cn("flex flex-col items-center justify-center py-20 px-6 text-center animate-fade-up", className)}>
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-surface-elevated mb-5">
        <Icon className="h-8 w-8 text-text-tertiary" strokeWidth={1.5} />
      </div>
      <h3 className="text-lg font-semibold font-display text-text-secondary mb-1.5">{title}</h3>
      <p className="text-sm text-text-tertiary max-w-sm mb-6">{description}</p>
      {action}
    </div>
  );
}
