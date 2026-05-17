"use client";

import { Clock, CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { getScannerRunStatus } from "@/lib/scans/lifecycle";

interface ScannerRun {
  id: string;
  scanner_name: string;
  status: string;
  scanner_version?: string;
  duration_ms?: number;
  error_message?: string;
  artifact_uri?: string | null;
  artifact_download_url?: string | null;
}

interface ScanTimelineProps {
  runs: ScannerRun[];
  scanStatus: string;
  className?: string;
}

const STATUS_ICONS = {
  active: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
  success: <CheckCircle2 className="h-4 w-4 text-success" />,
  error: <XCircle className="h-4 w-4 text-danger" />,
  pending: <Clock className="h-4 w-4 text-text-tertiary" />,
};

export function ScanTimeline({ runs, scanStatus, className }: ScanTimelineProps) {
  if (!runs || runs.length === 0) {
    const emptyMessage = scanStatus === "queued"
      ? "Waiting to start…"
      : scanStatus === "running"
        ? "Initializing scanner runs…"
        : "No scanner runs recorded.";
    return (
      <div className={cn("card-serif px-4 py-8 text-sm text-text-tertiary text-center", className)}>
        <AlertCircle className="h-5 w-5 mx-auto mb-2 opacity-50" />
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {runs.map((run, _idx) => {
        const statusInfo = getScannerRunStatus(run);
        return (
          <div key={run.id} className="card-serif p-4">
            <div className="flex items-center gap-3">
              {STATUS_ICONS[statusInfo.variant]}
              <span className="text-sm font-medium text-text-primary">{run.scanner_name}</span>
              {run.scanner_version && (
                <span className="text-xs font-mono text-text-tertiary">v{run.scanner_version}</span>
              )}
              <span className="ml-auto font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
                {run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : "—"}
              </span>
            </div>
            {run.error_message && (
              <div className="mt-3 rounded-[10px] border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
                {run.error_message}
              </div>
            )}
            {run.artifact_download_url && (
              <a
                href={run.artifact_download_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-2 text-sm text-primary hover:underline"
              >
                Download artifact
              </a>
            )}
          </div>
        );
      })}
    </div>
  );
}
