"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, RefreshCw, Trash2, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import {
  deriveScanPhase,
  canRerunScan,
  canDeleteScan,
  canCancelScan,
  deriveRerunPayload,
  formatScanSummary,
} from "@/lib/scans/lifecycle";
import { formatRelativeTime, formatScanDuration } from "@/lib/project-surface";
import { PageHeader } from "@/components/scanforge/page-header";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { ScanTimeline } from "@/components/scanforge/scan-timeline";
import { ScanSummaryCards } from "@/components/scanforge/scan-summary-cards";
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
      const payload = deriveRerunPayload({ repository_id: scan.repository_id, branch_name: scan.branch_name });
      const newScan = await api.scans.create(org_id, project_id, payload);
      router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${newScan.id}`);
    } catch {}
  }

  async function handleDelete() {
    if (!scan) return;
    if (!window.confirm("Delete this scan?")) {
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

  const phase = deriveScanPhase(scan);
  const summary = formatScanSummary(scan);
  const duration = formatScanDuration(scan.summary_json || {});

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
            {canRerunScan(scan.status) ? (
              <Button onClick={handleRerun}>
                <RefreshCw className="h-4 w-4" />
                Re-run
              </Button>
            ) : null}
            {canDeleteScan(scan.status) ? (
              <Button variant="outline" onClick={handleDelete}>
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            ) : null}
          </div>
        }
      />

      <ScanSummaryCards
        status={scan.status}
        branch={summary.branch}
        duration={duration}
        findingCount={summary.findingCount}
        className="mb-8"
      />

      {scan.error_message ? (
        <div className="mb-6 flex items-start gap-3 rounded-[10px] border border-danger/30 bg-danger/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <span className="text-sm text-danger">{scan.error_message}</span>
        </div>
      ) : null}

      <ScanTimeline
        runs={scan.scanner_runs || []}
        scanStatus={scan.status}
      />
    </div>
  );
}
