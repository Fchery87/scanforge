"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Database, Plus, Search } from "lucide-react";

import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/project-surface";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

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
    if (searchParams.get("connect") === "true") setShowModal(true);
  }, [searchParams]);

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.github.getIntegration(org_id as string).then(() => setHasGithub(true)).catch(() => setHasGithub(false));
  }, [org_id, project_id]);

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
              .then((stats) => {
                statsMap[repo.id] = stats;
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

  async function handleOpenModal() {
    setShowModal(true);
    if (hasGithub) {
      setLoadingGithubRepos(true);
      try {
        const res = await api.github.listRepositories(org_id as string);
        setGithubRepos(res.items ?? []);
      } catch (err: any) {
        setConnectError(err.message || "Failed to load repositories from GitHub");
      } finally {
        setLoadingGithubRepos(false);
      }
    }
  }

  async function handleConnectSelected() {
    setConnectingRepos(true);
    setConnectError("");
    const toConnect = githubRepos.filter((repo) => selectedRepos.has(repo.external_repo_id));
    const errors: string[] = [];

    await Promise.allSettled(
      toConnect.map((repo) =>
        api.repositories.create(org_id as string, project_id as string, {
          provider: "github",
          external_repo_id: repo.external_repo_id,
          owner_name: repo.owner_name,
          repo_name: repo.repo_name,
          full_name: repo.full_name,
          default_branch: repo.default_branch ?? "main",
          clone_url: repo.clone_url ?? "",
          html_url: repo.html_url ?? "",
        }).then((created) => setRepos((current) => [...current, created]))
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
  }

  const filteredConnectedRepos = repos.filter((repo) =>
    !repoFilter || repo.full_name?.toLowerCase().includes(repoFilter.toLowerCase())
  );

  const filteredGithubRepos = githubRepos.filter((repo) =>
    repo.full_name.toLowerCase().includes(repoSearch.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Repositories"
        description="Repositories connected to this project."
        actions={
          <Button onClick={handleOpenModal}>
            <Plus className="h-4 w-4" />
            Connect repository
          </Button>
        }
      />

      {loading ? (
        <SkeletonCards count={4} />
      ) : repos.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No repositories connected"
          description="Connect a repository, then start a scan."
          action={
            <Button onClick={handleOpenModal}>
              <Plus className="h-4 w-4" />
              Connect repository
            </Button>
          }
        />
      ) : (
        <>
          <div className="mb-6">
            <div className="relative max-w-md">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
              <Input
                placeholder="Filter repositories..."
                value={repoFilter}
                onChange={(e) => setRepoFilter(e.target.value)}
                className="h-11 bg-background pl-9"
              />
            </div>
          </div>

          <ul className="divide-y divide-border border-y border-border">
            {filteredConnectedRepos.map((repo) => {
              const stats = repoStats[repo.id];
              const statsUnavailable = repoStatsUnavailable[repo.id] ?? false;
              const open = stats?.open ?? 0;

              return (
                <li key={repo.id}>
                  <Link
                    href={`/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`}
                    className="flex items-baseline justify-between gap-4 py-3 hover-fine:bg-surface"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-text-primary">{repo.full_name ?? repo.repo_name}</span>
                      <span className="block truncate text-xs text-text-tertiary">
                        {repo.default_branch ?? "default branch"} · updated {formatRelativeTime(repo.updated_at ?? repo.created_at)}
                      </span>
                    </span>
                    <span className={open > 0 ? "shrink-0 font-mono text-sm text-primary" : "shrink-0 font-mono text-sm text-text-tertiary"}>
                      {statsUnavailable ? "—" : open}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>

          {filteredConnectedRepos.length === 0 && repoFilter ? (
            <div className="mt-8 text-center text-sm text-text-tertiary">
              No repositories match “{repoFilter}”.
            </div>
          ) : null}
        </>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Connect repository</DialogTitle>
            <DialogDescription>Select GitHub repositories to connect to this project.</DialogDescription>
          </DialogHeader>

          {hasGithub === null ? (
            <p className="py-4 text-sm text-text-tertiary">Checking GitHub connection...</p>
          ) : !hasGithub ? (
            <div className="space-y-4">
              <p className="text-sm text-text-secondary">No GitHub integration is configured for this organization.</p>
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
                <p className="py-4 text-sm text-text-tertiary">Loading repositories...</p>
              ) : (
                <div className="max-h-64 space-y-1 overflow-y-auto rounded-[10px] border border-border bg-background p-2">
                  {filteredGithubRepos.map((repo) => (
                    <label key={repo.external_repo_id} className="flex items-center gap-3 rounded-[8px] px-3 py-2 hover-fine:bg-surface-elevated">
                      <Checkbox
                        checked={selectedRepos.has(repo.external_repo_id)}
                        onCheckedChange={(checked) => {
                          const next = new Set(selectedRepos);
                          if (checked) {
                            next.add(repo.external_repo_id);
                          } else {
                            next.delete(repo.external_repo_id);
                          }
                          setSelectedRepos(next);
                        }}
                      />
                      <span className="flex-1 text-sm text-text-primary">{repo.full_name}</span>
                      {repo.private ? <Badge variant="outline">private</Badge> : null}
                    </label>
                  ))}
                </div>
              )}

              {connectError ? <p className="text-sm text-danger">{connectError}</p> : null}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => { setShowModal(false); setSelectedRepos(new Set()); }}>
                  Cancel
                </Button>
                <Button disabled={selectedRepos.size === 0 || connectingRepos} onClick={handleConnectSelected}>
                  {connectingRepos ? "Connecting..." : `Connect ${selectedRepos.size || ""} Repo${selectedRepos.size !== 1 ? "s" : ""}`}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
