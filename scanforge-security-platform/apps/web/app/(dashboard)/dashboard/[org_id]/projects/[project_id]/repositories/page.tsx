"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Database, GitBranch, ExternalLink, Plus, Calendar, Github } from "lucide-react";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import ScheduleSection from "./ScheduleSection";

export default function RepositoriesPage() {
  const { org_id, project_id } = useParams();
  const searchParams = useSearchParams();
  const [repos, setRepos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [expandedRepo, setExpandedRepo] = useState<string | null>(null);
  const [repoStats, setRepoStats] = useState<Record<string, any>>({});

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
        await Promise.allSettled(
          repoList.map((repo) =>
            api.findings.stats(org_id as string, project_id as string, { repositoryId: repo.id })
              .then((s) => { statsMap[repo.id] = s; })
              .catch(() => { statsMap[repo.id] = { open: 0 }; })
          )
        );
        setRepoStats(statsMap);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id, project_id]);

  const filteredRepos = githubRepos.filter((r) =>
    r.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Repositories"
        description={`${repos.length} connected repositories`}
        actions={
          <Button onClick={handleOpenModal}>
            <Plus className="h-4 w-4 mr-1" /> Connect Repository
          </Button>
        }
      />

      {loading ? (
        <SkeletonCards count={3} />
      ) : repos.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No repositories connected"
          description="Connect your first repository to start scanning"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {repos.map((repo) => (
            <div key={repo.id}>
              <Link
                href={`/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`}
                className="block rounded-xl border border-border bg-surface p-5 hover:border-border/80 hover:bg-surface-hover transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-elevated">
                    <Database className="h-5 w-5 text-text-secondary" strokeWidth={1.5} />
                  </div>
                  <Badge variant="outline" className="text-xs">{repo.provider}</Badge>
                </div>
                <h3 className="font-semibold text-text-primary mb-2">{repo.full_name}</h3>
                <div className="flex items-center gap-3 text-xs text-text-tertiary mb-3">
                  <span className="flex items-center gap-1"><GitBranch className="h-3.5 w-3.5" /> {repo.default_branch ?? "main"}</span>
                  <span className={cn(
                    "inline-flex items-center gap-1",
                    repo.is_active ? "text-success" : "text-text-tertiary"
                  )}>
                    <span className={cn("h-1.5 w-1.5 rounded-full", repo.is_active ? "bg-success" : "bg-text-tertiary")} />
                    {repo.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                {repoStats[repo.id] && (
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm font-medium text-text-primary">
                      {repoStats[repo.id].open ?? 0} open
                    </span>
                    {repoStats[repo.id].open > 0 && (
                      <span className="h-2 w-2 rounded-full bg-warning" />
                    )}
                  </div>
                )}
                {repo.html_url && (
                  <span
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink className="h-3 w-3" /> View on {repo.provider}
                  </span>
                )}
              </Link>
              <button
                className="w-full mt-1 flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs text-text-secondary hover:bg-surface-hover transition-colors"
                onClick={() => setExpandedRepo(expandedRepo === repo.id ? null : repo.id)}
              >
                <Calendar className="h-3.5 w-3.5" /> Schedules
              </button>
              {expandedRepo === repo.id && (
                <ScheduleSection
                  orgId={org_id as string}
                  projectId={project_id as string}
                  repoId={repo.id}
                  repoName={repo.full_name}
                />
              )}
            </div>
          ))}
        </div>
      )}

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
                  {filteredRepos.map((r) => (
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
