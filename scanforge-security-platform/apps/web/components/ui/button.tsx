"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 touch-target",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-white hover:bg-primary-hover shadow-sm hover:shadow-md hover:-translate-y-0.5 active:translate-y-0",
        destructive:
          "bg-red-900 text-white hover:bg-red-900/90 shadow-sm",
        outline:
          "border border-foreground bg-transparent text-foreground hover:bg-surface-hover hover:border-primary hover:text-primary",
        secondary:
          "bg-surface text-primary hover:bg-surface-hover border border-border",
        ghost:
          "text-text-secondary hover:text-foreground hover:underline decoration-primary underline-offset-4",
        link:
          "text-primary underline-offset-4 hover:underline",
        success:
          "bg-green-800 text-white hover:bg-green-800/90 shadow-sm",
      },
      size: {
        default: "h-12 px-6 py-2",
        sm: "h-10 px-4 text-xs",
        lg: "h-14 px-8 text-base",
        icon: "h-12 w-12",
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
