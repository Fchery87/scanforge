"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Clock, GitBranch, GitCommit, CheckCircle, XCircle, Loader, AlertTriangle, Download, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/scanforge/page-header";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function ScanDetailPage() {
  const { org_id, project_id, scan_id } = useParams<{ org_id: string; project_id: string; scan_id: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    api.scans.get(org_id, project_id, scan_id)
      .then((data) => {
        setScan(data);
        setLoadError("");
        setLoading(false);
      })
      .catch((err: any) => {
        setLoadError(err.message || "Failed to load scan");
        setLoading(false);
      });
  }, [org_id, project_id, scan_id]);

  useEffect(() => {
    if (!scan || !["queued", "running"].includes(scan.status)) return;
    const interval = setInterval(async () => {
      const updated = await api.scans.get(org_id, project_id, scan_id);
      setScan(updated);
      if (!["queued", "running"].includes(updated.status)) clearInterval(interval);
    }, 5000);
    return () => clearInterval(interval);
  }, [scan?.status]);

  const formatDuration = (ms: number | null) => {
    if (!ms) return "\u2014";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const handleRerun = async () => {
    if (!scan) return;
    try {
      const newScan = await api.scans.create(org_id, project_id, {
        repository_id: scan.repository_id,
        trigger_type: "manual",
        branch_name: scan.branch_name,
      });
      router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${newScan.id}`);
    } catch (err) { console.error(err); }
  };

  if (loading) return <SkeletonTable rows={5} />;
  if (loadError) return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <h2 className="text-xl font-semibold text-text-secondary">Scan unavailable</h2>
      <p className="mt-2 text-sm text-text-tertiary">{loadError}</p>
    </div>
  );
  if (!scan) return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <h2 className="text-xl font-semibold text-text-secondary">Scan not found</h2>
    </div>
  );

  const summary = scan.summary_json || {};

  return (
    <div>
      <Button variant="ghost" className="mb-4 gap-2" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4" /> Back to Scans
      </Button>

      <div className="flex items-start justify-between gap-4 mb-8">
        <div className="flex items-start gap-3">
          <StatusBadge status={scan.status} />
          <div>
            <h1 className="text-2xl font-bold font-display tracking-tight text-text-primary">
              Scan <code className="font-mono text-lg text-text-secondary">{scan.id?.slice(0, 8)}</code>
            </h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-text-tertiary">
              <span className="flex items-center gap-1"><GitBranch className="h-3.5 w-3.5" /> {scan.branch_name || "default"}</span>
              {scan.commit_sha && <span className="flex items-center gap-1"><GitCommit className="h-3.5 w-3.5" /> {scan.commit_sha.slice(0, 8)}</span>}
              <span>{scan.trigger_type}</span>
              <span>{new Date(scan.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {scan.status === "failed" && (
            <Button onClick={handleRerun}>
              <RefreshCw className="h-4 w-4 mr-1" /> Re-run
            </Button>
          )}
        </div>
      </div>

      {scan.status === "completed" && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-8">
          {[
            { label: "Total Findings", value: summary.finding_count ?? 0, color: "" },
            { label: "Critical", value: summary.critical_count ?? 0, color: "text-danger" },
            { label: "High", value: summary.high_count ?? 0, color: "text-warning" },
            { label: "Medium", value: summary.medium_count ?? 0, color: "" },
            { label: "Duration", value: summary.duration_seconds ? `${summary.duration_seconds}s` : (summary.duration_ms ? formatDuration(summary.duration_ms) : "\u2014"), color: "" },
          ].map((card) => (
            <div key={card.label} className="rounded-xl border border-border bg-surface p-4 text-center">
              <span className={cn("text-2xl font-bold font-display tracking-tight", card.color)}>{card.value}</span>
              <span className="block text-xs text-text-tertiary mt-1">{card.label}</span>
            </div>
          ))}
        </div>
      )}

      {scan.error_message && (
        <div className="flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 mb-6">
          <AlertTriangle className="h-5 w-5 text-danger flex-shrink-0 mt-0.5" />
          <span className="text-sm text-danger">{scan.error_message}</span>
        </div>
      )}

      <h3 className="text-lg font-semibold font-display text-text-primary mb-4">Scanner Runs</h3>
      <div className="space-y-3">
        {(!scan.scanner_runs || scan.scanner_runs.length === 0) && (
          <p className="text-sm text-text-tertiary py-4">
            {scan.status === "queued" ? "Waiting to start\u2026" : scan.status === "running" ? "Initializing scanner runs\u2026" : "No scanner runs recorded"}
          </p>
        )}
        {(scan.scanner_runs || []).map((run: any) => (
          <div key={run.id} className="rounded-xl border border-border bg-surface p-4">
            <div className="flex items-center gap-3">
              <StatusBadge status={run.status} />
              <span className="font-semibold text-text-primary">{run.scanner_name}</span>
              {run.scanner_version && <span className="text-xs text-text-tertiary font-mono">v{run.scanner_version}</span>}
              <span className="text-xs text-text-tertiary ml-auto">{formatDuration(run.duration_ms)}</span>
            </div>
            {run.error_message && (
              <div className="mt-2 rounded-lg bg-danger/10 border border-danger/20 p-3 text-sm text-danger">{run.error_message}</div>
            )}
            {run.artifact_uri && (
              <a href={run.artifact_uri} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 mt-2 text-sm text-primary hover:underline">
                <Download className="h-3.5 w-3.5" /> Download artifact
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
