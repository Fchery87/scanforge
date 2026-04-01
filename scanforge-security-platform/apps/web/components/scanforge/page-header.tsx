import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  eyebrow?: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  eyebrow,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "mb-8 flex flex-col gap-5 border-b border-border pb-6 md:flex-row md:items-end md:justify-between",
        className
      )}
    >
      <div className="animate-fade-up">
        {eyebrow && <p className="section-title mb-3">{eyebrow}</p>}
        <h1 className="page-title text-text-primary">
          {title}
        </h1>
        {description && (
          <p className="mt-3 max-w-[62ch] text-sm leading-relaxed text-text-secondary md:text-[0.95rem]">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 animate-fade-up">
          {actions}
        </div>
      )}
    </div>
  );
}
