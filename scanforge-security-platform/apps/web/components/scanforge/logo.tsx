import { cn } from "@/lib/utils";

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
      <path d="M5 5.5h8.25l5.25 5.25V18.5H10L5 13.5Z" />
      <path d="M9.5 5.5v5.5h5.5" />
      <path d="M7.5 15.75h6.75" />
      <path d="M7.5 12.5h3.25" />
      <path d="M15.75 7.5h2.75V10.25" />
    </svg>
  );
}
