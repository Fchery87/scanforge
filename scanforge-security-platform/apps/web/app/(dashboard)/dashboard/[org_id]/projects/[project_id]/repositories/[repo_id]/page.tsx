"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowLeft, Database, ExternalLink, GitBranch, Unlink } from "lucide-react";

import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/project-surface";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import ScheduleSection from "../ScheduleSection";

export default function RepoDetailPage() {
  const { org_id, project_id, repo_id } = useParams<{ org_id: string; project_id: string; repo_id: string }>();
  const router = useRouter();
  const [repo, setRepo] = useState<any>(null);
  const [scans, setScans] = useState<any[]>([]);
  const [repoStats, setRepoStats] = useState<any>(null);
  const [repoStatsUnavailable, setRepoStatsUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org_id || !project_id || !repo_id) return;
    Promise.allSettled([
      api.repositories.get(org_id, project_id, repo_id),
      api.scans.list(org_id, project_id, 0, 20),
      api.findings.stats(org_id, project_id, { repositoryId: repo_id }),
    ])
      .then(([repoResult, scansResult, statsResult]) => {
        if (repoResult.status === "fulfilled") setRepo(repoResult.value);
        if (scansResult.status === "fulfilled") {
          setScans((scansResult.value.items ?? []).filter((scan: any) => scan.repository_id === repo_id));
        }
        if (statsResult.status === "fulfilled") {
          setRepoStats(statsResult.value);
          setRepoStatsUnavailable(false);
        } else {
          setRepoStats(null);
          setRepoStatsUnavailable(true);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id, project_id, repo_id]);

  if (loading) return <SkeletonTable rows={5} />;
  if (!repo) return <EmptyState icon={Database} title="Repository not found" description="This repository could not be loaded." />;

  async function handleDisconnect() {
    if (!confirm(`Disconnect "${repo.full_name}"? This will not delete existing findings.`)) return;
    try {
      await api.repositories.remove(org_id, project_id, repo_id);
      router.push(`/dashboard/${org_id}/projects/${project_id}/repositories`);
    } catch {
      alert("Failed to disconnect repository");
    }
  }

  return (
    <div>
      <Button variant="ghost" className="mb-4 gap-2" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4" />
        Back to Repositories
      </Button>

      <PageHeader
        eyebrow="Repository"
        title={repo.full_name}
        description="Inspect scan history, findings volume, scheduling, and repository-level health for this codebase."
        actions={
          repo.html_url ? (
            <a href={repo.html_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm">
                <ExternalLink className="h-4 w-4" />
                View on {repo.provider}
              </Button>
            </a>
          ) : null
        }
      />

      <div className="mb-8 grid gap-4 md:grid-cols-4">
        <div className="card-serif p-4">
          <p className="section-title">Provider</p>
          <p className="mt-3 text-sm text-text-primary">{repo.provider}</p>
        </div>
        <div className="card-serif p-4">
          <p className="section-title">Default Branch</p>
          <p className="mt-3 inline-flex items-center gap-2 text-sm text-text-primary">
            <GitBranch className="h-4 w-4 text-text-tertiary" />
            {repo.default_branch ?? "main"}
          </p>
        </div>
        <div className="card-serif p-4">
          <p className="section-title">Open Findings</p>
          <p className="mt-3 font-display text-[1.8rem] leading-none text-text-primary">
            {repoStatsUnavailable ? "N/A" : repoStats?.open ?? 0}
          </p>
        </div>
        <div className="card-serif p-4">
          <p className="section-title">Recent Activity</p>
          <p className="mt-3 text-sm text-text-primary">
            {scans[0]?.created_at ? formatRelativeTime(scans[0].created_at) : "No scans yet"}
          </p>
        </div>
      </div>

      <div className="mb-6">
        <Link href={`/dashboard/${org_id}/projects/${project_id}/findings?repositoryId=${repo_id}`} className="text-sm text-primary hover:underline">
          View filtered findings for this repository →
        </Link>
      </div>

      {repoStatsUnavailable ? (
        <div className="mb-6 rounded-[10px] border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-secondary">
          Repository findings stats are temporarily unavailable.
        </div>
      ) : null}

      <div className="mb-8">
        <div className="mb-3 flex items-center justify-between">
          <p className="section-title">Scan History</p>
          <Badge variant="outline">{scans.length} recorded</Badge>
        </div>
        {scans.length === 0 ? (
          <EmptyState icon={Database} title="No scans recorded" description="Trigger a scan to begin repository-level monitoring." />
        ) : (
          <div className="space-y-3">
            {scans.slice(0, 10).map((scan) => (
              <Link
                key={scan.id}
                href={`/dashboard/${org_id}/projects/${project_id}/scans/${scan.id}`}
                className="card-serif card-interactive flex items-center gap-4 p-4"
              >
                <StatusBadge status={scan.status} />
                <code className="font-mono text-sm text-text-primary">{scan.id.slice(0, 8)}</code>
                <span className="flex-1 text-sm text-text-secondary">
                  {scan.trigger_type} · {scan.branch_name ?? "default"} · {new Date(scan.created_at).toLocaleDateString()}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="mb-8">
        <ScheduleSection orgId={org_id} projectId={project_id} repoId={repo_id} repoName={repo.full_name} />
      </div>

      <div className="rounded-[12px] border border-danger/30 bg-danger/5 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
          <div>
            <p className="text-sm font-semibold text-danger">Danger Zone</p>
            <p className="mt-1 text-sm text-text-secondary">
              Disconnecting will stop future scans but preserve existing findings and audit history.
            </p>
            <Button variant="destructive" size="sm" className="mt-4" onClick={handleDisconnect}>
              <Unlink className="h-4 w-4" />
              Disconnect Repository
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
