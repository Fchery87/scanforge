"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Activity, Play, Clock, CheckCircle, XCircle, Loader, Ban, Plus, XCircle as XCircleIcon } from "lucide-react";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export default function ScansPage() {
  const { org_id, project_id } = useParams();
  const router = useRouter();
  const [scans, setScans] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 20;
  const [showModal, setShowModal] = useState(false);
  const [repos, setRepos] = useState<any[]>([]);
  const [scanForm, setScanForm] = useState({
    repository_id: "",
    branch_name: "",
    scan_type: "full",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (showModal && repos.length === 0) {
      api.repositories.list(org_id as string, project_id as string).then((res: any) => {
        setRepos(res.items || res);
        if (res.items?.[0]) setScanForm((f) => ({ ...f, repository_id: res.items[0].id }));
      });
    }
  }, [showModal]);

  const handleTriggerScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scanForm.repository_id) return;
    setSubmitting(true);
    setError("");
    try {
      const scan = await api.scans.create(org_id as string, project_id as string, {
        repository_id: scanForm.repository_id,
        trigger_type: "manual",
        branch_name: scanForm.branch_name || undefined,
      });
      setScans((prev: any[]) => [scan, ...prev]);
      setShowModal(false);
      setScanForm({ repository_id: "", branch_name: "", scan_type: "full" });
    } catch (err: any) {
      setError(err.message || "Failed to trigger scan");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (scanId: string) => {
    try {
      const updated = await api.scans.cancel(org_id as string, project_id as string, scanId, "Canceled from UI");
      setScans((prev: any[]) => prev.map((s: any) => s.id === scanId ? updated : s));
    } catch (err) { console.error(err); }
  };

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.scans.list(org_id as string, project_id as string, page * limit, limit)
      .then((res) => {
        setScans(res.items ?? []);
        setTotal(res.total ?? 0);
        setLoading(false);
      }).catch(() => setLoading(false));
  }, [org_id, project_id, page]);

  function duration(scan: any) {
    if (!scan.summary_json?.duration_ms) return "\u2014";
    return `${(scan.summary_json.duration_ms / 1000).toFixed(1)}s`;
  }

  return (
    <div>
      <PageHeader
        title="Scans"
        description={`${total} total scan runs`}
        actions={
          <Button onClick={() => setShowModal(true)}>
            <Plus className="h-4 w-4 mr-1" /> Trigger Scan
          </Button>
        }
      />

      {loading ? (
        <SkeletonTable rows={5} />
      ) : scans.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No scans yet"
          description="Connect a repository and trigger your first scan"
        />
      ) : (
        <>
          <div className="rounded-xl border border-border bg-surface overflow-hidden">
            {scans.map((scan) => (
              <div
                key={scan.id}
                onClick={() => router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${scan.id}`)}
                className="flex items-center justify-between gap-4 px-4 py-3 border-b border-border/50 hover:bg-surface-hover cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <StatusBadge status={scan.status} />
                  <div className="min-w-0">
                    <span className="font-mono text-sm text-text-primary">{scan.id.slice(0, 8)}</span>
                    <span className="ml-2 text-xs text-text-tertiary">
                      {scan.trigger_type} · {scan.branch_name ?? "default"} · {new Date(scan.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {(scan.status === "queued" || scan.status === "running") && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-text-tertiary hover:text-danger"
                      onClick={(e) => { e.stopPropagation(); handleCancel(scan.id); }}
                      title="Cancel scan"
                    >
                      <XCircleIcon className="h-4 w-4" />
                    </Button>
                  )}
                  <span className="text-xs text-text-tertiary font-mono">{duration(scan)}</span>
                  {scan.scanner_runs?.map((run: any) => (
                    <span key={run.id} className="inline-flex items-center rounded-md border border-border bg-surface-elevated px-2 py-0.5 text-xs font-medium text-text-secondary">
                      {run.scanner_name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between py-4">
            <Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
            <span className="text-sm text-text-tertiary">
              {page * limit + 1}\u2013{Math.min((page + 1) * limit, total)} of {total}
            </span>
            <Button variant="ghost" disabled={(page + 1) * limit >= total} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Trigger Scan</DialogTitle>
            <DialogDescription>Start a new security scan for a connected repository.</DialogDescription>
          </DialogHeader>
          {error && <p className="text-sm text-danger">{error}</p>}
          <form onSubmit={handleTriggerScan} className="space-y-4">
            <div className="space-y-2">
              <Label>Repository</Label>
              <Select
                value={scanForm.repository_id}
                onValueChange={(val) => setScanForm({ ...scanForm, repository_id: val })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select repository…" />
                </SelectTrigger>
                <SelectContent>
                  {repos.map((r: any) => (
                    <SelectItem key={r.id} value={r.id}>{r.full_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Branch (optional)</Label>
              <Input
                value={scanForm.branch_name}
                onChange={(e) => setScanForm({ ...scanForm, branch_name: e.target.value })}
                placeholder="defaults to repo default branch"
              />
            </div>
            <div className="space-y-2">
              <Label>Scan Type</Label>
              <Select
                value={scanForm.scan_type}
                onValueChange={(val) => setScanForm({ ...scanForm, scan_type: val })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full">Full Scan</SelectItem>
                  <SelectItem value="dependencies">Dependencies Only</SelectItem>
                  <SelectItem value="secrets">Secrets Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Triggering\u2026" : "Start Scan"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
