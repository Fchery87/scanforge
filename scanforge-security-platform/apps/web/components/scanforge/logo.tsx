import { cn } from "@/lib/utils";

/**
 * ScanForgeLogo
 * Represents "The Target Hash" - a precise, brutalist brand mark 
 * fitting the Tactical Precision design system.
 */
export function ScanForgeLogo({ className }: { className?: string }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="1.5" 
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={cn("text-current", className)}
    >
      {/* Outer targeting chassis (sharp corners) */}
      <path d="M3 7V3h4 M17 3h4v4 M3 17v4h4 M17 21h4v-4" />
      {/* Inner data core */}
      <rect x="9" y="9" width="6" height="6" />
      {/* Precision laser grid */}
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
    </svg>
  );
}
