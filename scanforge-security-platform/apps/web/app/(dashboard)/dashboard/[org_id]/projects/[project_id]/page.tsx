"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FolderGit2, ShieldAlert } from "lucide-react";

import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/project-surface";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonStats } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";

export default function ProjectOverviewPage() {
  const { org_id, project_id } = useParams();
  const [project, setProject] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [repos, setRepos] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);
  const [urgent, setUrgent] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org_id || !project_id) return;

    Promise.all([
      api.projects.get(org_id as string, project_id as string),
      api.findings.stats(org_id as string, project_id as string),
      api.repositories.list(org_id as string, project_id as string).catch(() => null),
      api.auditLogs.listProject(org_id as string, project_id as string, 0, 6).catch(() => null),
      api.findings.list(org_id as string, project_id as string, { status: "open", severity: "critical", limit: "5" }).catch(() => null),
      api.findings.list(org_id as string, project_id as string, { status: "open", severity: "high", limit: "5" }).catch(() => null),
    ])
      .then(([projectData, statsData, reposData, activityData, critical, high]) => {
        setProject(projectData);
        setStats(statsData);
        setRepos(reposData?.items ?? []);
        setActivity(activityData?.items ?? []);
        setUrgent([...(critical?.items ?? []), ...(high?.items ?? [])].slice(0, 6));
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id, project_id]);

  if (loading) return <SkeletonStats count={4} />;
  if (!project) {
    return <EmptyState icon={ShieldAlert} title="Project unavailable" description="This project could not be loaded." />;
  }

  const critical = stats?.by_severity?.critical ?? 0;
  const high = stats?.by_severity?.high ?? 0;
  const findingsHref = `/dashboard/${org_id}/projects/${project_id}/findings`;

  return (
    <div>
      <PageHeader
        title={project.name}
        description="Critical and high findings that are still open. Everything else waits."
        actions={
          <Link href={findingsHref}>
            <Button size="sm">Review findings</Button>
          </Link>
        }
      />

      <div className="mb-8 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-4">
        <Count label="Critical" value={critical} emphasize={critical > 0} href={`${findingsHref}?severity=critical&status=open`} />
        <Count label="High" value={high} emphasize={high > 0} href={`${findingsHref}?severity=high&status=open`} />
        <Count label="Open" value={stats?.open ?? 0} href={`${findingsHref}?status=open`} />
        <Count label="Repositories" value={repos.length} href={`/dashboard/${org_id}/projects/${project_id}/repositories`} />
      </div>

      <section className="mb-10">
        <h2 className="mb-3 text-sm text-text-tertiary">Needs a decision</h2>
        {urgent.length === 0 ? (
          <p className="border-y border-border py-6 text-sm text-text-secondary">
            No open critical or high findings.
          </p>
        ) : (
          <ul className="divide-y divide-border border-y border-border">
            {urgent.map((finding) => (
              <li key={finding.id}>
                <Link href={`${findingsHref}?finding=${finding.id}`} className="flex items-baseline gap-4 py-3 hover-fine:bg-surface">
                  <span className={finding.severity === "critical" ? "w-16 shrink-0 text-xs text-primary" : "w-16 shrink-0 text-xs text-warning"}>
                    {finding.severity}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{finding.title ?? "Finding"}</span>
                  <span className="hidden shrink-0 truncate text-xs text-text-tertiary sm:block">
                    {finding.repository_name ?? finding.repository_id ?? "Unknown repository"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid gap-10 lg:grid-cols-2">
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-sm text-text-tertiary">Repositories</h2>
            <Link href={`/dashboard/${org_id}/projects/${project_id}/repositories`} className="text-sm text-text-secondary hover-fine:text-text-primary">
              All repositories
            </Link>
          </div>
          {repos.length === 0 ? (
            <EmptyState icon={FolderGit2} title="No repositories" description="Connect a repository before a scan can run." />
          ) : (
            <ul className="divide-y divide-border border-y border-border">
              {repos.slice(0, 6).map((repo) => (
                <li key={repo.id}>
                  <Link
                    href={`/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`}
                    className="flex items-baseline justify-between gap-3 py-2.5 hover-fine:bg-surface"
                  >
                    <span className="truncate text-sm text-text-primary">{repo.full_name ?? repo.repo_name}</span>
                    <span className="shrink-0 font-mono text-xs text-text-tertiary">{repo.default_branch ?? ""}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-sm text-text-tertiary">Recent activity</h2>
            <Link href={`/dashboard/${org_id}/audit-logs`} className="text-sm text-text-secondary hover-fine:text-text-primary">
              Audit log
            </Link>
          </div>
          {activity.length === 0 ? (
            <p className="text-sm text-text-tertiary">Nothing recorded yet.</p>
          ) : (
            <ul className="divide-y divide-border border-y border-border">
              {activity.map((item) => (
                <li key={item.id} className="flex items-baseline justify-between gap-3 py-2.5">
                  <span className="min-w-0 truncate text-sm text-text-primary">
                    {item.details?.title ?? item.details?.description ?? item.action}
                  </span>
                  <span className="shrink-0 font-mono text-xs text-text-tertiary">{formatRelativeTime(item.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Count({
  label,
  value,
  href,
  emphasize,
}: {
  label: string;
  value: number;
  href: string;
  emphasize?: boolean;
}) {
  return (
    <Link href={href} className="bg-background px-4 py-4 hover-fine:bg-surface">
      <p className="text-xs text-text-tertiary">{label}</p>
      <p className={`mt-1 font-mono text-[1.7rem] leading-none tracking-[-0.03em] ${emphasize ? "text-primary" : "text-text-primary"}`}>
        {value}
      </p>
    </Link>
  );
}
