import { cn } from "@/lib/utils";

export function SectionFrame({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <main className={cn("mx-auto w-full max-w-[1200px] px-5 py-6 md:px-8", className)}>
      {children}
    </main>
  );
}
