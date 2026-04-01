import { cn } from "@/lib/utils";

export function SectionFrame({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <main
      className={cn(
        "mx-auto w-full max-w-[var(--content-max-width)] px-4 py-6 md:px-6 md:py-8 lg:px-8",
        className
      )}
    >
      {children}
    </main>
  );
}
