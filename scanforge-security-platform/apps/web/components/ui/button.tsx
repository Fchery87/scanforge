"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "pressable inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[background-color,color,border-color,opacity] duration-150 ease-[var(--ease-out)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-white hover-fine:bg-primary-hover",
        destructive: "bg-danger text-white hover-fine:bg-danger/90",
        outline: "border border-border bg-transparent text-text-primary hover-fine:bg-surface-hover",
        secondary: "border border-border bg-surface text-text-primary hover-fine:bg-surface-hover",
        ghost: "text-text-secondary hover-fine:bg-surface-hover hover-fine:text-text-primary",
        link: "text-primary underline-offset-4 hover-fine:underline",
        success: "bg-success text-white hover-fine:bg-success/90",
      },
      size: {
        default: "h-9 px-3.5",
        sm: "h-8 px-3 text-[0.8125rem]",
        lg: "h-11 px-5",
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
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
