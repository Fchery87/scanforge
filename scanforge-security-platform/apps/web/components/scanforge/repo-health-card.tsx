import Link from "next/link";
import { Database, AlertTriangle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface RepoHealthCardProps {
  repoId: string;
  repoName: string;
  openFindings: number;
  criticalCount: number;
  href: string;
  className?: string;
}

export function RepoHealthCard({ repoName, openFindings, criticalCount, href, className }: RepoHealthCardProps) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-lg border border-border bg-surface p-3 transition-all duration-200 hover:border-border-strong hover:bg-surface-hover group",
        className
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <Database className="h-3.5 w-3.5 text-primary flex-shrink-0" />
        <span className="text-xs font-semibold text-text-primary truncate">{repoName}</span>
      </div>
      <div className="flex gap-2 items-center">
        {openFindings === 0 ? (
          <span className="flex items-center gap-1 text-[11px] text-success font-medium">
            <CheckCircle className="h-3 w-3" /> clean
          </span>
        ) : (
          <span className="text-[11px] text-warning font-medium">{openFindings} open</span>
        )}
        {criticalCount > 0 && (
          <span className="flex items-center gap-1 text-[11px] text-danger font-medium">
            <AlertTriangle className="h-3 w-3" /> {criticalCount} critical
          </span>
        )}
      </div>
    </Link>
  );
}
