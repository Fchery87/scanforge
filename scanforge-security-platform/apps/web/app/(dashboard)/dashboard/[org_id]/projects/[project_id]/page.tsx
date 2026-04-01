"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Activity, ArrowRight, FolderGit2, ShieldAlert, TrendingUp } from "lucide-react";

import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/project-surface";
import { EmptyState } from "@/components/scanforge/empty-state";
import { FindingsBarChart } from "@/components/scanforge/findings-bar-chart";
import { PageHeader } from "@/components/scanforge/page-header";
import { RiskScoreGauge } from "@/components/scanforge/risk-score-gauge";
import { SeverityBreakdown } from "@/components/scanforge/severity-breakdown";
import { SkeletonStats } from "@/components/scanforge/loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function ProjectOverviewPage() {
  const { org_id, project_id } = useParams();
  const [project, setProject] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [scorecard, setScorecard] = useState<any>(null);
  const [trend, setTrend] = useState<any>(null);
  const [repos, setRepos] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);
  const [topFindings, setTopFindings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org_id || !project_id) return;

    Promise.all([
      api.projects.get(org_id as string, project_id as string),
      api.findings.stats(org_id as string, project_id as string),
      api.scorecard.get(org_id as string, project_id as string).catch(() => null),
      api.findings.trend(org_id as string, project_id as string, 30).catch(() => null),
      api.repositories.list(org_id as string, project_id as string).catch(() => null),
      api.auditLogs.listProject(org_id as string, project_id as string, 0, 6).catch(() => null),
      api.findings.list(org_id as string, project_id as string, { severity: "critical", limit: "3" }).catch(() => null),
      api.findings.list(org_id as string, project_id as string, { severity: "high", limit: "3" }).catch(() => null),
    ])
      .then(([
        projectData,
        statsData,
        scorecardData,
        trendData,
        reposData,
        activityData,
        criticalFindings,
        highFindings,
      ]) => {
        setProject(projectData);
        setStats(statsData);
        setScorecard(scorecardData);
        setTrend(trendData);
        setRepos(reposData?.items ?? []);
        setActivity(activityData?.items ?? []);
        setTopFindings((criticalFindings?.items?.length ? criticalFindings.items : highFindings?.items) ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id, project_id]);

  if (loading) return <SkeletonStats count={4} />;
  if (!project) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Project unavailable"
        description="This project could not be loaded."
      />
    );
  }

  const highPriorityCount = (stats?.by_severity?.critical ?? 0) + (stats?.by_severity?.high ?? 0);

  return (
    <div>
      <PageHeader
        eyebrow="Project"
        title={project.name ?? "Security Overview"}
        description="Monitor risk posture, repository coverage, critical findings, and the most recent security activity for this project."
        actions={
          <>
            <Link href={`/dashboard/${org_id}/projects/${project_id}/findings`}>
              <Button variant="outline" size="sm">Open Findings</Button>
            </Link>
            <Link href={`/dashboard/${org_id}/projects/${project_id}/scans`}>
              <Button size="sm">Runbooks & Scans</Button>
            </Link>
          </>
        }
      />

      <div className="mb-8 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="card-serif p-6">
          <p className="section-title mb-3">Current Exposure</p>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="font-display text-[3rem] leading-none tracking-[-0.04em] text-text-primary">
                {stats?.open ?? 0}
              </p>
              <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.14em] text-text-tertiary">
                Open Findings
              </p>
            </div>
            <div className="md:col-span-2">
              <SeverityBreakdown
                critical={stats?.by_severity?.critical ?? 0}
                high={stats?.by_severity?.high ?? 0}
                medium={stats?.by_severity?.medium ?? 0}
                low={stats?.by_severity?.low ?? 0}
              />
            </div>
          </div>
          <div className="mt-5 flex items-center gap-2 text-sm text-text-secondary">
            <TrendingUp className="h-4 w-4 text-primary" />
            Trend reflects the last 30 days of normalized scanner output.
          </div>
        </div>

        <div className="card-serif flex flex-col gap-4 p-6">
          <p className="section-title">Risk Score</p>
          <div className="flex flex-1 items-center justify-center">
            <RiskScoreGauge score={scorecard?.overall_score ?? 0} />
          </div>
          <div className="flex items-center justify-between border-t border-border pt-4">
            <span className="text-sm text-text-secondary">Repositories in scope</span>
            <Badge variant="outline">{repos.length} connected</Badge>
          </div>
        </div>
      </div>

      <div className="mb-8 grid gap-4 lg:grid-cols-[1fr_360px]">
        <FindingsBarChart data={trend?.data ?? []} />

        <div className="card-serif p-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="section-title">High Priority</p>
            <Badge variant={highPriorityCount > 0 ? "warning" : "default"}>
              {highPriorityCount} requiring review
            </Badge>
          </div>

          {topFindings.length === 0 ? (
            <p className="text-sm text-text-tertiary">No critical or high-priority findings are open right now.</p>
          ) : (
            <div className="space-y-3">
              {topFindings.map((finding) => (
                <Link
                  key={finding.id}
                  href={`/dashboard/${org_id}/projects/${project_id}/findings`}
                  className="block rounded-[10px] border border-border bg-background px-4 py-3 transition-colors hover:border-border-strong hover:bg-surface-elevated"
                >
                  <p className="text-sm font-medium text-text-primary">{finding.title ?? "Security finding"}</p>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {finding.repository_name ?? finding.repository_id ?? finding.primary_scanner ?? "Unknown source"}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <p className="section-title">Repositories</p>
            <Link href={`/dashboard/${org_id}/projects/${project_id}/repositories`} className="text-sm text-primary">
              View all
            </Link>
          </div>
          <div className="space-y-3">
            {repos.length === 0 ? (
              <EmptyState
                icon={FolderGit2}
                title="No repositories connected"
                description="Connect a repository to begin scanning and trend collection."
              />
            ) : (
              repos.slice(0, 4).map((repo) => (
                <Link
                  key={repo.id}
                  href={`/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`}
                  className="card-serif card-interactive flex items-center gap-4 p-4"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-border bg-background text-primary">
                    <FolderGit2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text-primary">{repo.full_name ?? repo.repo_name}</p>
                    <p className="mt-1 text-xs text-text-tertiary">{repo.default_branch ?? "default branch"}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-text-tertiary" />
                </Link>
              ))
            )}
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <p className="section-title">Recent Activity</p>
            <Link href={`/dashboard/${org_id}/audit-logs`} className="text-sm text-primary">
              Audit log
            </Link>
          </div>
          <div className="card-serif overflow-hidden">
            {activity.length === 0 ? (
              <div className="px-4 py-8 text-sm text-text-tertiary">No recent activity recorded yet.</div>
            ) : (
              activity.map((item) => (
                <div key={item.id} className="flex items-start gap-3 border-b border-border/60 px-4 py-4 last:border-0">
                  <span className="mt-2 h-2 w-2 rounded-full bg-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text-primary">{item.details?.title ?? item.details?.description ?? item.action}</p>
                    <p className="mt-1 text-xs text-text-tertiary">{formatRelativeTime(item.created_at)}</p>
                  </div>
                  <Activity className="h-4 w-4 text-text-tertiary" />
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
