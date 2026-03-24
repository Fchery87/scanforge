"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";
import { Shield, AlertTriangle, CheckCircle, Clock, Activity, Search, ArrowRight, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/scanforge/page-header";
import { StatCard } from "@/components/scanforge/stat-card";
import { ScorecardRing } from "@/components/scanforge/scorecard-ring";
import { TrendChart } from "@/components/scanforge/trend-chart";
import { ScheduleIndicator } from "@/components/scanforge/schedule-indicator";
import { RepoHealthCard } from "@/components/scanforge/repo-health-card";
import { SkeletonStats, SkeletonList } from "@/components/scanforge/loading-skeleton";
import { cn } from "@/lib/utils";

export default function ProjectOverviewPage() {
  const { org_id, project_id } = useParams();
  const [project, setProject] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [scans, setScans] = useState<any[]>([]);
  const [scorecard, setScorecard] = useState<any>(null);
  const [trend, setTrend] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [repoStats, setRepoStats] = useState<Record<string, any>>({});
  const [repos, setRepos] = useState<any[]>([]);
  const [hasSchedules, setHasSchedules] = useState<boolean | null>(null);

  useEffect(() => {
    if (!org_id || !project_id) return;
    Promise.all([
      api.projects.get(org_id as string, project_id as string),
      api.findings.stats(org_id as string, project_id as string),
      api.scans.list(org_id as string, project_id as string, 0, 5),
      api.scorecard.get(org_id as string, project_id as string).catch(() => null),
      api.findings.trend(org_id as string, project_id as string, 30).catch(() => null),
      api.repositories.list(org_id as string, project_id as string).catch(() => null),
    ]).then(async ([projData, statsData, scansData, scorecardData, trendData, reposData]) => {
      setProject(projData);
      setStats(statsData);
      setScans(scansData.items ?? []);
      if (scorecardData) setScorecard(scorecardData);
      if (trendData) setTrend(trendData);
      if (reposData) {
        const repoList = reposData.items ?? [];
        setRepos(repoList);
        // Check schedules
        for (const r of repoList.slice(0, 3)) {
          try {
            const schedules: any = await api.schedules.list(org_id as string, project_id as string, r.id);
            if ((Array.isArray(schedules) ? schedules : schedules?.items ?? []).length > 0) {
              setHasSchedules(true);
              break;
            }
          } catch {}
        }
        if (hasSchedules === null) setHasSchedules(false);
        // Fetch repo stats
        const statsMap: Record<string, any> = {};
        await Promise.allSettled(
          repoList.map((r: any) =>
            api.findings.stats(org_id as string, project_id as string, { repositoryId: r.id })
              .then((s: any) => { statsMap[r.id] = s; })
              .catch(() => { statsMap[r.id] = null; })
          )
        );
        setRepoStats(statsMap);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [org_id, project_id]);

  if (loading) return <SkeletonStats count={4} />;

  const severityColors: Record<string, string> = {
    critical: "text-danger",
    high: "text-severity-high",
    medium: "text-warning",
    low: "text-success",
    info: "text-primary",
  };

  const severityBorders: Record<string, string> = {
    critical: "border-danger/30",
    high: "border-severity-high/30",
    medium: "border-warning/30",
    low: "border-success/30",
    info: "border-primary/30",
  };

  return (
    <div>
      <PageHeader
        title={project?.name ?? "Project"}
        description={project?.description}
        actions={
          <Link href={`/dashboard/${org_id}/projects/${project_id}/repositories?connect=true`}>
            <Button><Database className="h-4 w-4" /> Connect Repository</Button>
          </Link>
        }
      />

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4 animate-fade-up stagger-1">
        <StatCard icon={Shield} value={stats?.open ?? 0} label="Open Findings" variant="warning" />
        <StatCard icon={AlertTriangle} value={stats?.by_severity?.critical ?? 0} label="Critical" variant="danger" />
        <StatCard icon={CheckCircle} value={stats?.fixed ?? 0} label="Fixed" variant="success" />
        <StatCard icon={Activity} value={stats?.suppressed ?? 0} label="Suppressed" variant="primary" />
      </div>

      {/* Severity Pills */}
      <div className="flex gap-2 mb-6 flex-wrap animate-fade-up stagger-2">
        {["critical", "high", "medium", "low", "info"].map((sev) => (
          <div
            key={sev}
            className={cn(
              "flex items-center gap-2 rounded-full border bg-surface px-3.5 py-1.5 text-sm capitalize transition-colors hover:border-border-strong",
              severityBorders[sev]
            )}
          >
            <span className="text-text-secondary">{sev}</span>
            <strong className={cn("text-sm font-bold", severityColors[sev])}>{stats?.by_severity?.[sev] ?? 0}</strong>
          </div>
        ))}
      </div>

      {/* Schedule Indicator */}
      {hasSchedules !== null && (
        <ScheduleIndicator
          hasSchedules={hasSchedules}
          orgId={org_id as string}
          projectId={project_id as string}
          className="mb-4"
        />
      )}

      {/* Scorecard Banner */}
      {scorecard && (
        <div className="grid grid-cols-1 md:grid-cols-[auto_1fr_auto] gap-4 md:gap-6 items-center rounded-xl border border-border bg-surface p-5 mb-4 animate-fade-up stagger-3">
          <ScorecardRing grade={scorecard.grade} overallScore={scorecard.overall_score} />
          <div className="space-y-2">
            {[
              { label: "Overall", score: scorecard.overall_score },
              { label: "Security", score: scorecard.security_score },
              { label: "Secrets", score: scorecard.secrets_score },
              { label: "Dependencies", score: scorecard.dependency_score },
            ].map((row) => (
              <div key={row.label} className="flex items-center gap-3">
                <span className="text-xs text-text-secondary w-24">{row.label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-surface-elevated overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary to-success transition-all duration-700"
                    style={{ width: `${row.score}%` }}
                  />
                </div>
                <span className="text-xs font-mono font-semibold w-8 text-right">{row.score}</span>
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-3 pl-5 border-l border-border text-center">
            <div>
              <span className="text-lg font-bold font-display block">{scorecard.new_this_week}</span>
              <span className="text-[10px] text-text-tertiary">New This Week</span>
            </div>
            <div>
              <span className="text-lg font-bold font-display block">{scorecard.fixed_30d}</span>
              <span className="text-[10px] text-text-tertiary">Fixed (30d)</span>
            </div>
            <div>
              <span className="text-lg font-bold font-display block">{scorecard.scan_count}</span>
              <span className="text-[10px] text-text-tertiary">Total Scans</span>
            </div>
          </div>
        </div>
      )}

      {/* Trend Chart */}
      {trend && trend.data && (
        <div className="mb-6 animate-fade-up stagger-4">
          <h3 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">Findings Trend (30 days)</h3>
          <TrendChart data={trend.data} />
        </div>
      )}

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Scans */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Recent Scans</h2>
            <Link href={`/dashboard/${org_id}/projects/${project_id}/scans`} className="text-xs text-primary hover:underline font-medium">View all</Link>
          </div>
          {scans.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 rounded-xl border border-dashed border-border bg-surface text-text-tertiary">
              <Clock className="h-8 w-8 mb-2" strokeWidth={1.5} />
              <p className="text-sm">No scans yet</p>
            </div>
          ) : (
            <div className="space-y-1.5">
              {scans.map((scan) => (
                <Link
                  key={scan.id}
                  href={`/dashboard/${org_id}/projects/${project_id}/scans`}
                  className="group flex items-center gap-3 rounded-lg border border-border bg-surface px-3.5 py-3 transition-all hover:border-border-strong"
                >
                  <div
                    className={cn(
                      "h-2 w-2 rounded-full flex-shrink-0",
                      scan.status === "completed" && "bg-success",
                      scan.status === "failed" && "bg-danger",
                      scan.status === "running" && "bg-primary animate-glow-pulse",
                      scan.status === "queued" && "bg-text-tertiary",
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-text-primary block truncate">{scan.repository_id}</span>
                    <span className="text-[11px] text-text-tertiary font-mono">{new Date(scan.created_at).toLocaleString()}</span>
                  </div>
                  <Badge variant="default" className="capitalize">{scan.trigger_type}</Badge>
                  <ArrowRight className="h-3.5 w-3.5 text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Quick Links */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Quick Access</h2>
          </div>
          <div className="space-y-1.5">
            {[
              { href: `/dashboard/${org_id}/projects/${project_id}/findings?severity=critical`, icon: AlertTriangle, iconColor: "text-danger", label: "Critical Findings" },
              { href: `/dashboard/${org_id}/projects/${project_id}/findings?category=secret`, icon: Shield, iconColor: "text-warning", label: "Secret Findings" },
              { href: `/dashboard/${org_id}/projects/${project_id}/findings?category=vulnerability`, icon: AlertTriangle, iconColor: "text-secondary", label: "Vulnerabilities" },
              { href: `/dashboard/${org_id}/projects/${project_id}/exports`, icon: Search, iconColor: "text-primary", label: "Generate Export" },
            ].map((link) => (
              <Link
                key={link.label}
                href={link.href}
                className="group flex items-center gap-3 rounded-lg border border-border bg-surface px-3.5 py-3 text-sm font-medium text-text-secondary transition-all hover:border-border-strong hover:text-text-primary"
              >
                <link.icon className={cn("h-4 w-4 flex-shrink-0", link.iconColor)} />
                <span className="flex-1">{link.label}</span>
                <ArrowRight className="h-3.5 w-3.5 text-text-tertiary opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        </div>

        {/* Repository Health */}
        {repos.length > 0 && (
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Repository Health</h2>
              <Link href={`/dashboard/${org_id}/projects/${project_id}/repositories`} className="text-xs text-primary hover:underline font-medium">View all</Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {repos.slice(0, 6).map((repo) => {
                const s = repoStats[repo.id];
                return (
                  <RepoHealthCard
                    key={repo.id}
                    repoId={repo.id}
                    repoName={repo.full_name}
                    openFindings={s?.open ?? 0}
                    criticalCount={s?.by_severity?.critical ?? 0}
                    href={`/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`}
                  />
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
