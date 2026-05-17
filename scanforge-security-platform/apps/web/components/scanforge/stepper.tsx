"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Step {
  id: string;
  label: string;
  description?: string;
  completed: boolean;
}

interface StepperProps {
  steps: Step[];
  currentStep?: number;
  className?: string;
}

export function Stepper({ steps, currentStep = 0, className }: StepperProps) {
  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <div className={cn("relative", className)}>
      {/* Progress bar background */}
      <div className="absolute top-5 left-0 right-0 h-0.5 bg-border -translate-y-1/2" />
      
      {/* Progress bar fill */}
      <div
        className="absolute top-5 left-0 h-0.5 bg-primary -translate-y-1/2 transition-all duration-500 ease-out"
        style={{ width: `${Math.max(0, progress - (100 / steps.length) / 2)}%` }}
      />

      {/* Steps */}
      <div className="relative flex justify-between">
        {steps.map((step, index) => {
          const isCompleted = step.completed;
          const isCurrent = index === currentStep;
          const isUpcoming = index > currentStep;

          return (
            <div key={step.id} className="flex flex-col items-center">
              {/* Step circle */}
              <div
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 z-10",
                  isCompleted && [
                    "bg-success border-success text-white",
                    "shadow-lg shadow-success/20"
                  ],
                  isCurrent && [
                    "bg-primary border-primary text-white scale-110",
                    "shadow-lg shadow-primary/30",
                    "ring-4 ring-primary/10"
                  ],
                  isUpcoming && [
                    "bg-surface border-border text-text-tertiary"
                  ]
                )}
              >
                {isCompleted ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <span className="text-sm font-semibold">{index + 1}</span>
                )}
              </div>

              {/* Label */}
              <span
                className={cn(
                  "mt-2 text-xs font-medium text-center max-w-[100px] transition-colors duration-300",
                  isCompleted && "text-success",
                  isCurrent && "text-primary",
                  isUpcoming && "text-text-tertiary"
                )}
              >
                {step.label}
              </span>

              {/* Description */}
              {step.description && (
                <span className="mt-0.5 text-[10px] text-text-tertiary text-center max-w-[120px]">
                  {step.description}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Celebration confetti effect
export function triggerCelebration() {
  if (typeof window === "undefined") return;

  // Dynamic import to avoid SSR issues
  import("canvas-confetti").then((confetti) => {
    const defaults = {
      origin: { y: 0.7 },
      colors: ["#B8860B", "#D4A84B", "#8B0000", "#2D5A3D"],
    };

    const fire = (particleRatio: number, opts: any) => {
      confetti.default({
        ...defaults,
        ...opts,
        particleCount: Math.floor(200 * particleRatio),
      });
    };

    fire(0.25, { spread: 26, startVelocity: 55 });
    fire(0.2, { spread: 60 });
    fire(0.35, { spread: 100, decay: 0.91, scalar: 0.8 });
    fire(0.1, { spread: 120, startVelocity: 25, decay: 0.92, scalar: 1.2 });
    fire(0.1, { spread: 120, startVelocity: 45 });
  });
}

// Completion badge
interface CompletionBadgeProps {
  percentage: number;
  className?: string;
}

export function CompletionBadge({ percentage, className }: CompletionBadgeProps) {
  const circumference = 2 * Math.PI * 18;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)}>
      <svg className="w-12 h-12 -rotate-90">
        <circle
          cx="24"
          cy="24"
          r="18"
          fill="none"
          stroke="var(--color-border)"
          strokeWidth="3"
        />
        <circle
          cx="24"
          cy="24"
          r="18"
          fill="none"
          stroke="var(--color-primary)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <span className="absolute text-xs font-bold text-primary">
        {percentage}%
      </span>
    </div>
  );
}
