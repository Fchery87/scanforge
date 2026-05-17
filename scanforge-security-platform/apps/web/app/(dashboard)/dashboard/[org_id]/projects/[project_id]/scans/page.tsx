"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Activity, Plus, Trash2, XCircle as XCircleIcon } from "lucide-react";

import { api } from "@/lib/api";
import { canDeleteScan, canCancelScan, deriveScanPhase } from "@/lib/scans/lifecycle";
import { formatRelativeTime, formatScanDuration } from "@/lib/project-surface";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
  const [scanForm, setScanForm] = useState({ repository_id: "", branch_name: "", scan_type: "full" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [reposError, setReposError] = useState("");
  const [filterRepoId, setFilterRepoId] = useState<string>("all");

  useEffect(() => {
    if (showModal && repos.length === 0) {
      api.repositories.list(org_id as string, project_id as string)
        .then((res: any) => {
          setRepos(res.items || res);
          setReposError("");
          if (res.items?.[0]) {
            setScanForm((current) => ({ ...current, repository_id: res.items[0].id }));
          }
        })
        .catch((err: any) => setReposError(err.message || "Failed to load repositories"));
    }
  }, [showModal, org_id, project_id, repos.length]);

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.scans.list(org_id as string, project_id as string, page * limit, limit)
      .then((res) => {
        setScans(res.items ?? []);
        setTotal(res.total ?? 0);
        setListError("");
        setLoading(false);
      })
      .catch((err: any) => {
        setListError(err.message || "Failed to load scans");
        setLoading(false);
      });
  }, [org_id, project_id, page]);

  async function handleTriggerScan(e: React.FormEvent) {
    e.preventDefault();
    if (!scanForm.repository_id) return;
    setSubmitting(true);
    setError("");
    try {
      const scan = await api.scans.create(org_id as string, project_id as string, {
        repository_id: scanForm.repository_id,
        trigger_type: "manual",
        branch_name: scanForm.branch_name || undefined,
        scan_type: scanForm.scan_type,
      });
      setScans((current: any[]) => [scan, ...current]);
      setShowModal(false);
      setScanForm({ repository_id: "", branch_name: "", scan_type: "full" });
    } catch (err: any) {
      setError(err.message || "Failed to trigger scan");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel(scanId: string) {
    try {
      const updated = await api.scans.cancel(org_id as string, project_id as string, scanId, "Canceled from UI");
      setScans((current: any[]) => current.map((scan: any) => scan.id === scanId ? updated : scan));
    } catch {
      // ignore
    }
  }

  async function handleDelete(scanId: string) {
    if (!window.confirm("Delete this scan?")) {
      return;
    }
    try {
      await api.scans.delete(org_id as string, project_id as string, scanId);
      setScans((current: any[]) => current.filter((scan: any) => scan.id !== scanId));
      setTotal((current) => Math.max(0, current - 1));
    } catch {
      // ignore
    }
  }

  const filteredScans = filterRepoId === "all"
    ? scans
    : scans.filter((scan) => scan.repository_id === filterRepoId);

  const uniqueRepos = Array.from(
    new Map(scans.map((s) => [s.repository_id, s.repository_name || s.repository_id])).entries()
  ).map(([id, name]) => ({ id, name }));

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Scans"
        description={`${total} total scan runs with execution state, timing, and scanner coverage for this project.`}
        actions={
          <Button onClick={() => setShowModal(true)}>
            <Plus className="h-4 w-4" />
            Trigger Scan
          </Button>
        }
      />

      {loading ? (
        <SkeletonTable rows={5} />
      ) : listError ? (
        <EmptyState icon={Activity} title="Scans unavailable" description={listError} />
      ) : scans.length === 0 ? (
        <EmptyState icon={Activity} title="No scans yet" description="Connect a repository and trigger your first scan." />
      ) : (
        <>
          {uniqueRepos.length > 1 && (
            <div className="mb-4 flex items-center gap-3">
              <label className="text-sm text-text-secondary">Repository</label>
              <Select value={filterRepoId} onValueChange={setFilterRepoId}>
                <SelectTrigger className="w-[280px]">
                  <SelectValue placeholder="All repositories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All repositories</SelectItem>
                  {uniqueRepos.map((repo) => (
                    <SelectItem key={repo.id} value={repo.id}>{repo.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="card-serif overflow-hidden">
            {filteredScans.map((scan) => {
              const phase = deriveScanPhase(scan);
              const isFailedOrStale = phase === "failed" || phase === "stale";
              return (
                <div
                  key={scan.id}
                  onClick={() => router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${scan.id}`)}
                  className={`flex cursor-pointer items-center justify-between gap-4 border-b border-border/60 px-4 py-4 transition-colors last:border-0 ${
                    isFailedOrStale
                      ? "hover:bg-danger/[0.03] border-l-2 border-l-danger/30 bg-danger/[0.02]"
                      : "hover:bg-surface-hover/45"
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-3">
                      <StatusBadge status={phase === "stale" ? "failed" : scan.status} />
                      <code className="font-mono text-sm text-text-primary">{scan.id.slice(0, 8)}</code>
                      <span className="text-xs text-text-tertiary">{scan.trigger_type}</span>
                      {phase === "stale" ? <Badge variant="danger">stale</Badge> : null}
                    </div>
                    <p className="mt-2 text-sm text-text-secondary">
                      {scan.branch_name ?? "default branch"} · created {formatRelativeTime(scan.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {(scan.scanner_runs ?? []).slice(0, 3).map((run: any) => (
                      <Badge key={run.id} variant="outline">{run.scanner_name}</Badge>
                    ))}
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
                      {formatScanDuration(scan.summary_json ?? {})}
                    </span>
                    {canCancelScan(scan.status) ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 text-text-tertiary hover:text-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCancel(scan.id);
                        }}
                      >
                        <XCircleIcon className="h-4 w-4" />
                      </Button>
                    ) : null}
                    {canDeleteScan(scan.status) ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-9 w-9 text-text-tertiary hover:text-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(scan.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between py-4">
            <Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
            <span className="text-sm text-text-tertiary">
              {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}
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
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {reposError ? <p className="text-sm text-danger">{reposError}</p> : null}
          <form onSubmit={handleTriggerScan} className="space-y-4">
            <div className="space-y-2">
              <Label>Repository</Label>
              <Select value={scanForm.repository_id} onValueChange={(val) => setScanForm({ ...scanForm, repository_id: val })} disabled={!!reposError}>
                <SelectTrigger><SelectValue placeholder="Select repository…" /></SelectTrigger>
                <SelectContent>
                  {repos.map((repo: any) => (
                    <SelectItem key={repo.id} value={repo.id}>{repo.full_name}</SelectItem>
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
              <Select value={scanForm.scan_type} onValueChange={(val) => setScanForm({ ...scanForm, scan_type: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="full">Full Scan</SelectItem>
                  <SelectItem value="dependencies">Dependencies Only</SelectItem>
                  <SelectItem value="secrets">Secrets Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button type="submit" disabled={submitting}>{submitting ? "Triggering…" : "Start Scan"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
