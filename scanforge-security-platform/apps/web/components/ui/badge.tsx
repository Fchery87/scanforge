import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium font-display transition-all duration-200",
  {
    variants: {
      variant: {
        default: "border-border bg-surface-elevated/50 text-text-secondary",
        primary: "border-primary/25 bg-primary/8 text-primary",
        secondary: "border-secondary/25 bg-secondary/8 text-secondary",
        success: "border-success/25 bg-success/8 text-success",
        warning: "border-warning/25 bg-warning/8 text-warning",
        danger: "border-danger/25 bg-danger/8 text-danger",
        info: "border-info/25 bg-info/8 text-info",
        outline: "border-border text-text-secondary",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
