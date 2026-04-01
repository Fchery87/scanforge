"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, Download, ExternalLink, RefreshCw, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { deriveScanLifecycle } from "@/lib/page-surface/contracts";
import { formatRelativeTime, formatScanDuration } from "@/lib/project-surface";
import { PageHeader } from "@/components/scanforge/page-header";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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
  }, [scan, org_id, project_id, scan_id]);

  async function handleRerun() {
    if (!scan) return;
    try {
      const newScan = await api.scans.create(org_id, project_id, {
        repository_id: scan.repository_id,
        trigger_type: "manual",
        branch_name: scan.branch_name,
      });
      router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${newScan.id}`);
    } catch {}
  }

  async function handleDelete() {
    if (!scan) return;
    if (!window.confirm("Delete this stale scan? Completed scans are retained and cannot be deleted.")) {
      return;
    }

    try {
      await api.scans.delete(org_id, project_id, scan_id);
      router.push(`/dashboard/${org_id}/projects/${project_id}/scans`);
    } catch {}
  }

  if (loading) return <SkeletonTable rows={5} />;
  if (loadError || !scan) {
    return (
      <div className="py-20 text-center">
        <p className="text-xl font-semibold text-text-secondary">Scan unavailable</p>
        <p className="mt-2 text-sm text-text-tertiary">{loadError || "This scan could not be found."}</p>
      </div>
    );
  }

  const summary = scan.summary_json || {};
  const lifecycle = deriveScanLifecycle(scan);

  return (
    <div>
      <Button variant="ghost" className="mb-4 gap-2" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4" />
        Back to Scans
      </Button>

      <PageHeader
        eyebrow="Scan"
        title={`Scan ${scan.id?.slice(0, 8)}`}
        description={`Run status, scanner breakdown, and artifacts for the scan created ${formatRelativeTime(scan.created_at)}.`}
        actions={
          <div className="flex items-center gap-2">
            {lifecycle.canRerun ? (
              <Button onClick={handleRerun}>
                <RefreshCw className="h-4 w-4" />
                Re-run
              </Button>
            ) : null}
            {lifecycle.canDelete ? (
              <Button variant="outline" onClick={handleDelete}>
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="mb-8 grid gap-4 md:grid-cols-4">
        <div className="card-serif p-4">
          <p className="section-title">Status</p>
          <div className="mt-3"><StatusBadge status={scan.status} /></div>
        </div>
        <div className="card-serif p-4">
          <p className="section-title">Branch</p>
          <p className="mt-3 text-sm text-text-primary">{scan.branch_name || "default"}</p>
        </div>
        <div className="card-serif p-4">
          <p className="section-title">Duration</p>
          <p className="mt-3 text-sm text-text-primary">{formatScanDuration(summary)}</p>
        </div>
        <div className="card-serif p-4">
          <p className="section-title">Findings</p>
          <p className="mt-3 font-display text-[1.8rem] leading-none text-text-primary">{summary.finding_count ?? 0}</p>
        </div>
      </div>

      {scan.error_message ? (
        <div className="mb-6 flex items-start gap-3 rounded-[10px] border border-danger/30 bg-danger/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <span className="text-sm text-danger">{scan.error_message}</span>
        </div>
      ) : null}

      <div className="space-y-3">
        <p className="section-title">Scanner Runs</p>
        {(!scan.scanner_runs || scan.scanner_runs.length === 0) ? (
          <div className="card-serif px-4 py-8 text-sm text-text-tertiary">
            {scan.status === "queued"
              ? "Waiting to start…"
              : scan.status === "running"
                ? "Initializing scanner runs…"
                : "No scanner runs recorded."}
          </div>
        ) : (
          scan.scanner_runs.map((run: any) => (
            <div key={run.id} className="card-serif p-4">
              <div className="flex items-center gap-3">
                <StatusBadge status={run.status} />
                <span className="text-sm font-medium text-text-primary">{run.scanner_name}</span>
                {run.scanner_version ? <Badge variant="outline">v{run.scanner_version}</Badge> : null}
                <span className="ml-auto font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
                  {formatScanDuration({ duration_ms: run.duration_ms })}
                </span>
              </div>
              {run.error_message ? (
                <div className="mt-3 rounded-[10px] border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
                  {run.error_message}
                </div>
              ) : null}
              {run.artifact_uri ? (
                <a href={run.artifact_uri} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm text-primary">
                  <Download className="h-4 w-4" />
                  Download artifact
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
