"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Plus, Search } from "lucide-react";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Database } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

// ─── Helpers ────────────────────────────────────────────────────────────────

function getRepoIcon(name: string): { icon: string; bg: string; color: string } {
  const lower = name.toLowerCase();
  if (lower.includes("python") || lower.includes("api") || lower.includes("backend"))
    return { icon: "🐍", bg: "bg-success/10", color: "text-success" };
  if (lower.includes("frontend") || lower.includes("web") || lower.includes("react") || lower.includes("next"))
    return { icon: "⚛", bg: "bg-info/10", color: "text-info" };
  if (lower.includes("go") || lower.includes("service"))
    return { icon: "🔷", bg: "bg-accent/10", color: "text-accent" };
  if (lower.includes("data") || lower.includes("pipeline"))
    return { icon: "📊", bg: "bg-warning/10", color: "text-warning" };
  return { icon: "📦", bg: "bg-secondary/10", color: "text-secondary" };
}

function deriveGrade(stats: any): string {
  if (!stats) return "—";
  const penalty = (stats.by_severity?.critical ?? 0) * 25 + (stats.open ?? 0) * 3;
  const score = Math.max(0, 100 - penalty);
  if (score >= 95) return "A+";
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

function gradeBadgeClasses(grade: string): string {
  if (grade.startsWith("A")) return "bg-success text-white";
  if (grade === "B") return "bg-primary text-white";
  if (grade === "C") return "bg-warning text-white";
  if (grade === "D") return "bg-severity-high text-white";
  return "bg-danger text-white";
}

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function RepositoriesPage() {
  const { org_id, project_id } = useParams();
  const searchParams = useSearchParams();
  const [repos, setRepos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [repoStats, setRepoStats] = useState<Record<string, any>>({});
  const [repoStatsUnavailable, setRepoStatsUnavailable] = useState<Record<string, boolean>>({});
  const [repoFilter, setRepoFilter] = useState("");

  const [githubRepos, setGithubRepos] = useState<any[]>([]);
  const [repoSearch, setRepoSearch] = useState("");
  const [selectedRepos, setSelectedRepos] = useState<Set<string>>(new Set());
  const [loadingGithubRepos, setLoadingGithubRepos] = useState(false);
  const [connectingRepos, setConnectingRepos] = useState(false);
  const [connectError, setConnectError] = useState("");
  const [hasGithub, setHasGithub] = useState<boolean | null>(null);

  useEffect(() => {
    if (searchParams.get("connect") === "true") {
      setShowModal(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.github.getIntegration(org_id as string)
      .then(() => setHasGithub(true))
      .catch(() => setHasGithub(false));
  }, [org_id]);

  const handleOpenModal = async () => {
    setShowModal(true);
    if (hasGithub) {
      setLoadingGithubRepos(true);
      try {
        const res = await api.github.listRepositories(org_id as string);
        setGithubRepos(res.items ?? []);
      } catch (err: any) {
        console.error("Failed to load GitHub repositories:", err);
        setConnectError(err.message || "Failed to load repositories from GitHub");
      } finally {
        setLoadingGithubRepos(false);
      }
    }
  };

  const handleConnectSelected = async () => {
    setConnectingRepos(true);
    setConnectError("");
    const toConnect = githubRepos.filter((r) => selectedRepos.has(r.external_repo_id));
    const errors: string[] = [];

    await Promise.allSettled(
      toConnect.map((r) =>
        api.repositories
          .create(org_id as string, project_id as string, {
            provider: "github",
            external_repo_id: r.external_repo_id,
            owner_name: r.owner_name,
            repo_name: r.repo_name,
            full_name: r.full_name,
            default_branch: r.default_branch ?? "main",
            clone_url: r.clone_url ?? "",
            html_url: r.html_url ?? "",
          })
          .then((repo) => setRepos((prev) => [...prev, repo]))
          .catch((err) => errors.push(err.message))
      )
    );

    setConnectingRepos(false);
    if (errors.length === 0) {
      setShowModal(false);
      setSelectedRepos(new Set());
    } else {
      setConnectError(`${errors.length} repo(s) failed: ${errors[0]}`);
    }
  };

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.repositories.list(org_id as string, project_id as string)
      .then(async (res) => {
        const repoList = res.items ?? [];
        setRepos(repoList);
        const statsMap: Record<string, any> = {};
        const unavailableMap: Record<string, boolean> = {};
        await Promise.allSettled(
          repoList.map((repo) =>
            api.findings.stats(org_id as string, project_id as string, { repositoryId: repo.id })
              .then((s) => {
                statsMap[repo.id] = s;
                unavailableMap[repo.id] = false;
              })
              .catch(() => {
                statsMap[repo.id] = null;
                unavailableMap[repo.id] = true;
              })
          )
        );
        setRepoStats(statsMap);
        setRepoStatsUnavailable(unavailableMap);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id, project_id]);

  const filteredGithubRepos = githubRepos.filter((r) =>
    r.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  const filteredConnectedRepos = repos.filter((r) =>
    !repoFilter || r.full_name?.toLowerCase().includes(repoFilter.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Connected Repositories Workspace"
        description="Continuous code repository monitoring and vulnerability management."
        actions={
          <Button onClick={handleOpenModal} className="bg-primary hover:bg-primary/90 text-white">
            <Plus className="h-4 w-4 mr-1" /> Connect Repository
          </Button>
        }
      />

      {loading ? (
        <SkeletonCards count={4} />
      ) : repos.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No repositories connected"
          description="Connect your first repository to start scanning"
        />
      ) : (
        <div className="space-y-4">
          {/* Search bar */}
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary pointer-events-none" />
            <Input
              placeholder="Filter repositories..."
              value={repoFilter}
              onChange={(e) => setRepoFilter(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Repository card grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {filteredConnectedRepos.map((repo) => {
              const icon = getRepoIcon(repo.full_name ?? repo.repo_name ?? "");
              const stats = repoStats[repo.id];
              const statsUnavailable = repoStatsUnavailable[repo.id] ?? false;
              const grade = deriveGrade(stats);
              const lastScanDate = repo.updated_at ?? repo.created_at;
              const lastScanLabel = lastScanDate ? timeAgo(lastScanDate) : "Never";

              return (
                <Link
                  key={repo.id}
                  href={`/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`}
                  className="rounded-xl border border-border bg-surface p-4 hover:border-border-strong hover:bg-surface-hover transition-all group flex items-center gap-4"
                >
                  {/* Tech icon */}
                  <div
                    className={cn(
                      "h-10 w-10 rounded-lg flex items-center justify-center flex-shrink-0 text-lg",
                      icon.bg
                    )}
                    aria-hidden="true"
                  >
                    {icon.icon}
                  </div>

                  {/* Repo info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-text-primary truncate leading-tight">
                      {repo.full_name ?? repo.repo_name}
                    </p>
                    <p className="text-xs text-text-tertiary mt-0.5">
                      Last scan: {lastScanLabel}
                      {statsUnavailable && " · stats unavailable"}
                    </p>
                  </div>

                  {/* Letter grade badge */}
                  <div
                    className={cn(
                      "h-8 w-8 rounded-full text-xs font-bold font-display flex items-center justify-center flex-shrink-0",
                      statsUnavailable || grade === "—"
                        ? "bg-surface-elevated text-text-tertiary"
                        : gradeBadgeClasses(grade)
                    )}
                    aria-label={statsUnavailable ? "Security grade unavailable" : `Security grade: ${grade}`}
                  >
                    {statsUnavailable ? "?" : grade}
                  </div>
                </Link>
              );
            })}
          </div>

          {filteredConnectedRepos.length === 0 && repoFilter && (
            <p className="text-sm text-text-tertiary text-center py-8">
              No repositories match &ldquo;{repoFilter}&rdquo;
            </p>
          )}

          {Object.values(repoStatsUnavailable).some(Boolean) && (
            <div className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-secondary">
              Some repository grades are unavailable because findings stats could not be loaded.
            </div>
          )}
        </div>
      )}

      {/* Connect Repository dialog */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Connect Repository</DialogTitle>
            <DialogDescription>Select GitHub repositories to connect to this project.</DialogDescription>
          </DialogHeader>

          {hasGithub === null ? (
            <p className="text-sm text-text-tertiary py-4">Checking GitHub connection...</p>
          ) : !hasGithub ? (
            <div className="space-y-4">
              <p className="text-sm text-text-secondary">No GitHub integration found.</p>
              <p className="text-sm">
                Go to{" "}
                <Link href={`/dashboard/${org_id}/settings#integrations`} className="text-primary hover:underline">
                  Organization Settings &rarr; Integrations
                </Link>{" "}
                to connect GitHub first.
              </p>
              <div className="flex justify-end">
                <Button variant="ghost" onClick={() => setShowModal(false)}>Close</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <Input
                placeholder="Search repositories..."
                value={repoSearch}
                onChange={(e) => setRepoSearch(e.target.value)}
              />

              {loadingGithubRepos ? (
                <p className="text-sm text-text-tertiary py-4">Loading repositories...</p>
              ) : (
                <div className="max-h-64 overflow-y-auto space-y-1 rounded-lg border border-border">
                  {filteredGithubRepos.map((r) => (
                    <label
                      key={r.external_repo_id}
                      className="flex items-center gap-3 px-3 py-2 hover:bg-surface-hover cursor-pointer"
                    >
                      <Checkbox
                        checked={selectedRepos.has(r.external_repo_id)}
                        onCheckedChange={(checked) => {
                          const next = new Set(selectedRepos);
                          checked ? next.add(r.external_repo_id) : next.delete(r.external_repo_id);
                          setSelectedRepos(next);
                        }}
                      />
                      <span className="text-sm text-text-primary flex-1">{r.full_name}</span>
                      {r.private && <Badge variant="outline" className="text-xs">private</Badge>}
                    </label>
                  ))}
                </div>
              )}

              {connectError && <p className="text-sm text-danger">{connectError}</p>}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => { setShowModal(false); setSelectedRepos(new Set()); }}>
                  Cancel
                </Button>
                <Button
                  disabled={selectedRepos.size === 0 || connectingRepos}
                  onClick={handleConnectSelected}
                >
                  {connectingRepos
                    ? "Connecting..."
                    : `Connect ${selectedRepos.size > 0 ? selectedRepos.size : ""} Repo${selectedRepos.size !== 1 ? "s" : ""}`}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
