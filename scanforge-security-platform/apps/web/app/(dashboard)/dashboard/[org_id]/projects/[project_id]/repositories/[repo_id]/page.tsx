"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Database, GitBranch, ExternalLink, CheckCircle, XCircle, AlertTriangle, Unlink } from "lucide-react";
import { api } from "@/lib/api";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { EmptyState } from "@/components/scanforge/empty-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import ScheduleSection from "../ScheduleSection";

export default function RepoDetailPage() {
  const { org_id, project_id, repo_id } = useParams<{ org_id: string; project_id: string; repo_id: string }>();
  const router = useRouter();
  const [repo, setRepo] = useState<any>(null);
  const [scans, setScans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org_id || !project_id || !repo_id) return;
    Promise.all([
      api.repositories.list(org_id, project_id).then((res: any) => {
        const found = (res.items ?? []).find((r: any) => r.id === repo_id);
        setRepo(found);
      }),
      api.scans.list(org_id, project_id, 0, 20).then((res: any) => {
        setScans((res.items ?? []).filter((s: any) => s.repository_id === repo_id));
      }),
    ]).then(() => setLoading(false)).catch(() => setLoading(false));
  }, [org_id, project_id, repo_id]);

  if (loading) return <SkeletonTable rows={5} />;
  if (!repo) return <EmptyState icon={Database} title="Repository not found" description="This repository could not be loaded." />;

  const handleDisconnect = async () => {
    if (!confirm(`Disconnect "${repo.full_name}"? This will not delete existing findings.`)) return;
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
      await fetch(`${API_BASE}/api/v1/organizations/${org_id}/projects/${project_id}/repositories/${repo_id}`, {
        method: "DELETE",
        credentials: "include",
      });
      router.push(`/dashboard/${org_id}/projects/${project_id}/repositories`);
    } catch {
      alert("Failed to disconnect repository");
    }
  };

  return (
    <div>
      <Button variant="ghost" className="mb-4 gap-2" onClick={() => router.back()}>
        <ArrowLeft className="h-4 w-4" /> Back to Repositories
      </Button>

      <div className="flex items-start gap-4 mb-8">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-elevated">
          <Database className="h-6 w-6 text-text-secondary" strokeWidth={1.5} />
        </div>
        <div>
          <h1 className="text-2xl font-bold font-display tracking-tight text-text-primary">{repo.full_name}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-text-tertiary">
            <Badge variant="outline" className="text-xs">{repo.provider}</Badge>
            <span className="flex items-center gap-1"><GitBranch className="h-3.5 w-3.5" /> {repo.default_branch ?? "main"}</span>
            <span className={cn("flex items-center gap-1", repo.is_active ? "text-success" : "text-text-tertiary")}>
              {repo.is_active ? <CheckCircle className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
              {repo.is_active ? "Active" : "Inactive"}
            </span>
          </div>
          {repo.html_url && (
            <a href={repo.html_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 mt-2 text-sm text-primary hover:underline">
              <ExternalLink className="h-3.5 w-3.5" /> View on {repo.provider}
            </a>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {[
          { label: "Total Scans", value: scans.length },
          { label: "Completed", value: scans.filter((s) => s.status === "completed").length },
          { label: "Failed", value: scans.filter((s) => s.status === "failed").length },
          { label: "Filtered Findings", value: <Link href={`/dashboard/${org_id}/projects/${project_id}/findings?repositoryId=${repo_id}`} className="text-primary hover:underline">View Findings &rarr;</Link> },
        ].map((stat) => (
          <div key={stat.label} className="rounded-xl border border-border bg-surface p-4 text-center">
            <span className="text-2xl font-bold font-display tracking-tight">{stat.value}</span>
            <span className="block text-xs text-text-tertiary mt-1">{stat.label}</span>
          </div>
        ))}
      </div>

      <div className="mb-8">
        <h3 className="text-lg font-semibold font-display text-text-primary mb-4">Scan History</h3>
        {scans.length === 0 ? (
          <p className="text-sm text-text-tertiary py-4">No scans recorded for this repository</p>
        ) : (
          <div className="space-y-2">
            {scans.slice(0, 10).map((scan) => (
              <Link
                key={scan.id}
                href={`/dashboard/${org_id}/projects/${project_id}/scans/${scan.id}`}
                className="flex items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3 hover:bg-surface-hover transition-colors"
              >
                <StatusBadge status={scan.status} />
                <code className="font-mono text-sm text-text-secondary">{scan.id.slice(0, 8)}</code>
                <span className="text-sm text-text-tertiary flex-1">
                  {scan.trigger_type} · {scan.branch_name ?? "default"} · {new Date(scan.created_at).toLocaleDateString()}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="mb-8">
        <ScheduleSection
          orgId={org_id as string}
          projectId={project_id as string}
          repoId={repo_id as string}
          repoName={repo.full_name}
        />
      </div>

      <div className="rounded-xl border border-danger/30 bg-danger/5 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-danger flex-shrink-0 mt-0.5" />
          <div>
            <span className="text-sm font-semibold text-danger">Danger Zone</span>
            <p className="text-sm text-text-secondary mt-1">Disconnecting will stop future scans but preserve existing findings.</p>
            <Button variant="destructive" size="sm" className="mt-3" onClick={handleDisconnect}>
              <Unlink className="h-4 w-4 mr-1" /> Disconnect Repository
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
