"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium font-display transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 active:scale-[0.97]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-white shadow-lg shadow-primary/20 hover:bg-primary-hover hover:shadow-xl hover:shadow-primary/30 hover:glow-wire",
        destructive:
          "bg-danger text-white shadow-lg shadow-danger/20 hover:shadow-xl hover:shadow-danger/30",
        outline:
          "border border-border bg-transparent text-text-secondary hover:bg-surface-hover hover:text-text-primary hover:border-border-strong hover:glow-wire",
        secondary:
          "bg-gradient-to-r from-secondary to-secondary-hover text-white shadow-lg shadow-secondary/20 hover:shadow-xl hover:shadow-secondary/30",
        ghost:
          "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
        link:
          "text-primary underline-offset-4 hover:underline",
        success:
          "bg-success text-white shadow-lg shadow-success/20 hover:shadow-xl hover:shadow-success/30",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-lg px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
