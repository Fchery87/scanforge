import Link from "next/link";
import { AlertTriangle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ScheduleIndicatorProps {
  hasSchedules: boolean;
  orgId: string;
  projectId: string;
  className?: string;
}

export function ScheduleIndicator({ hasSchedules, orgId, projectId, className }: ScheduleIndicatorProps) {
  if (hasSchedules) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-success", className)}>
        <CheckCircle className="h-4 w-4" />
        <span>Automated scanning is active</span>
      </div>
    );
  }

  return (
    <div className={cn("flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-2.5 text-sm text-warning", className)}>
      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
      <span>No scan schedules configured.</span>
      <Link
        href={`/dashboard/${orgId}/projects/${projectId}/repositories`}
        className="text-primary font-medium hover:underline ml-1"
      >
        Set up automated scanning →
      </Link>
    </div>
  );
}
