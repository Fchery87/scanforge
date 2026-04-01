"use client";

import { useState, forwardRef } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface FloatingInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const FloatingInput = forwardRef<HTMLInputElement, FloatingInputProps>(
  ({ label, error, className, ...props }, ref) => {
    const [isFocused, setIsFocused] = useState(false);
    const hasValue = !!props.value;

    return (
      <div className="relative">
        <input
          ref={ref}
          {...props}
          className={cn(
            "peer w-full rounded-lg border bg-surface px-4 pt-6 pb-2 text-sm",
            "transition-all duration-200 outline-none",
            "placeholder-transparent",
            "focus:border-primary focus:ring-2 focus:ring-primary/10",
            error && [
              "border-danger focus:border-danger focus:ring-danger/10",
              "bg-danger/5"
            ],
            !error && "border-border hover:border-border-strong",
            className
          )}
          placeholder={label}
          onFocus={(e) => {
            setIsFocused(true);
            props.onFocus?.(e);
          }}
          onBlur={(e) => {
            setIsFocused(false);
            props.onBlur?.(e);
          }}
        />
        <label
          className={cn(
            "absolute left-4 transition-all duration-200 pointer-events-none",
            "text-text-tertiary",
            (isFocused || hasValue) && [
              "top-1.5 text-[10px] text-primary font-medium",
              error && "text-danger"
            ],
            !isFocused && !hasValue && "top-4 text-sm"
          )}
        >
          {label}
        </label>
        
        {error && (
          <span className="mt-1.5 text-xs text-danger flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {error}
          </span>
        )}
      </div>
    );
  }
);

FloatingInput.displayName = "FloatingInput";

// Enhanced button with loading state
interface LoadingButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  loadingText?: string;
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

export function LoadingButton({
  loading,
  loadingText,
  children,
  variant = "primary",
  size = "md",
  disabled,
  className,
  ...props
}: LoadingButtonProps) {
  const baseStyles = cn(
    "relative inline-flex items-center justify-center",
    "font-medium transition-all duration-200",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    "focus:outline-none focus:ring-2 focus:ring-offset-2",
    size === "sm" && "px-3 py-1.5 text-xs rounded-md",
    size === "md" && "px-4 py-2 text-sm rounded-lg",
    size === "lg" && "px-6 py-3 text-base rounded-lg",
    variant === "primary" && [
      "bg-primary text-white",
      "hover:bg-primary-hover",
      "focus:ring-primary/50"
    ],
    variant === "secondary" && [
      "bg-surface-elevated text-text-primary border border-border",
      "hover:bg-surface-hover",
      "focus:ring-border-strong/50"
    ],
    variant === "outline" && [
      "bg-transparent text-text-primary border border-border",
      "hover:bg-surface-hover",
      "focus:ring-border-strong/50"
    ],
    variant === "ghost" && [
      "bg-transparent text-text-secondary",
      "hover:bg-surface-hover hover:text-text-primary",
      "focus:ring-border-strong/50"
    ],
    variant === "danger" && [
      "bg-danger text-white",
      "hover:bg-danger/90",
      "focus:ring-danger/50"
    ],
    className
  );

  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={baseStyles}
    >
      {loading && (
        <span className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="h-4 w-4 animate-spin" />
        </span>
      )}
      <span className={cn(loading && "opacity-0")}>
        {loading && loadingText ? loadingText : children}
      </span>
    </button>
  );
}

// Form section with header
interface FormSectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export function FormSection({ title, description, children, className }: FormSectionProps) {
  return (
    <div className={cn("space-y-4", className)}>
      <div>
        <h3 className="text-base font-semibold font-display text-text-primary">{title}</h3>
        {description && (
          <p className="text-sm text-text-secondary mt-1">{description}</p>
        )}
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}
