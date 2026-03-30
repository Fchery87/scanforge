"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { TrendingUp, ScanLine, ShieldAlert, UserCog, Activity } from "lucide-react";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonStats } from "@/components/scanforge/loading-skeleton";
import { RiskScoreGauge } from "@/components/scanforge/risk-score-gauge";
import { FindingsBarChart } from "@/components/scanforge/findings-bar-chart";
import { SeverityBreakdown } from "@/components/scanforge/severity-breakdown";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

function activityDot(action: string): string {
  if (action?.includes("scan")) return "bg-success";
  if (action?.includes("finding") || action?.includes("vuln")) return "bg-danger";
  return "bg-primary";
}

function activityIcon(action: string) {
  if (action?.includes("scan")) return ScanLine;
  if (action?.includes("finding") || action?.includes("vuln")) return ShieldAlert;
  return UserCog;
}

function formatActivityLabel(item: any): string {
  const action: string = item.action ?? "";
  if (action.includes("scan_created")) return `New scan started for ${item.resource_id ?? "repository"}`;
  if (action.includes("scan_completed")) return `Scan completed — ${item.details?.findings_count ?? 0} findings`;
  if (action.includes("finding")) return item.details?.title ?? "Finding updated";
  if (action.includes("user")) return item.details?.description ?? "User action performed";
  return item.details?.description ?? action.replace(/_/g, " ");
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProjectOverviewPage() {
  const { org_id, project_id } = useParams();

  const [project, setProject]           = useState<any>(null);
  const [stats, setStats]               = useState<any>(null);
  const [scans, setScans]               = useState<any[]>([]);
  const [scorecard, setScorecard]       = useState<any>(null);
  const [trend, setTrend]               = useState<any>(null);
  const [repos, setRepos]               = useState<any[]>([]);
  const [repoStats, setRepoStats]       = useState<Record<string, any>>({});
  const [activity, setActivity]         = useState<any[]>([]);
  const [topFindings, setTopFindings]   = useState<any[]>([]);
  const [loading, setLoading]           = useState(true);

  useEffect(() => {
    if (!org_id || !project_id) return;

    Promise.all([
      api.projects.get(org_id as string, project_id as string),
      api.findings.stats(org_id as string, project_id as string),
      api.scans.list(org_id as string, project_id as string, 0, 5),
      api.scorecard.get(org_id as string, project_id as string).catch(() => null),
      api.findings.trend(org_id as string, project_id as string, 30).catch(() => null),
      api.repositories.list(org_id as string, project_id as string).catch(() => null),
      api.auditLogs.listProject(org_id as string, project_id as string, 0, 5).catch(() => null),
      api.findings.list(org_id as string, project_id as string, { severity: "critical", limit: "3" }).catch(() => null),
      api.findings.list(org_id as string, project_id as string, { severity: "high", limit: "3" }).catch(() => null),
    ]).then(async ([
      projData,
      statsData,
      scansData,
      scorecardData,
      trendData,
      reposData,
      activityData,
      topFindingsData,
      topHighFindingsData,
    ]) => {
      setProject(projData);
      setStats(statsData);
      setScans(scansData.items ?? []);
      if (scorecardData) setScorecard(scorecardData);
      if (trendData) setTrend(trendData);
      if (activityData) setActivity(activityData.items ?? []);
      const criticalFindings = topFindingsData?.items ?? [];
      const highFindings = topHighFindingsData?.items ?? [];
      setTopFindings(criticalFindings.length > 0 ? criticalFindings : highFindings);

      if (reposData) {
        const repoList = reposData.items ?? [];
        setRepos(repoList);
        const statsMap: Record<string, any> = {};
        await Promise.allSettled(
          repoList.map((r: any) =>
            api.findings
              .stats(org_id as string, project_id as string, { repositoryId: r.id })
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

  const highPriorityCount =
    (stats?.by_severity?.critical ?? 0) + (stats?.by_severity?.high ?? 0);

  // Build Top Alerts from real findings only. Prefer critical, then high.
  const topAlerts: { label: string; sub: string }[] =
    topFindings.slice(0, 3).map((f) => ({
      label: f.title ?? "Security finding",
      sub: f.repository_name ?? f.repository_id ?? f.primary_scanner ?? "Unknown source",
    }));

  return (
    <div>
      <PageHeader title="Security Overview Dashboard" />

      {/* ------------------------------------------------------------------ */}
      {/* Top 3 cards                                                         */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 animate-fade-up stagger-1">

        {/* Card 1 – Total Vulnerabilities */}
        <div className="rounded-xl border border-border bg-surface p-5">
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            Total Vulnerabilities
          </p>

          <p className="text-4xl font-bold font-display text-text-primary mb-4">
            {stats?.open ?? 0}
          </p>

          <SeverityBreakdown
            critical={stats?.by_severity?.critical ?? 0}
            high={stats?.by_severity?.high ?? 0}
            medium={stats?.by_severity?.medium ?? 0}
            low={stats?.by_severity?.low ?? 0}
            className="mb-4"
          />

          <div className="flex items-center gap-1.5 text-xs text-primary font-medium">
            <TrendingUp className="h-3.5 w-3.5" />
            <span>Trend — 12 months</span>
          </div>
        </div>

        {/* Card 2 – Risk Score */}
        <div className="rounded-xl border border-border bg-surface p-5 flex flex-col">
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            Risk Score
          </p>
          <div className="flex flex-1 items-center justify-center">
            <RiskScoreGauge score={scorecard?.overall_score ?? 0} />
          </div>
        </div>

        {/* Card 3 – High Priority Findings */}
        <div className="rounded-xl border border-border bg-surface p-5">
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">
            High Priority Findings
          </p>

          <p className={cn("text-4xl font-bold font-display mb-4", highPriorityCount > 0 ? "text-severity-high" : "text-text-primary")}>
            {highPriorityCount}
          </p>

          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
            Top Alerts
          </p>

          {topAlerts.length === 0 ? (
            <p className="text-xs text-text-tertiary">No critical or high findings detected.</p>
          ) : (
            <ul className="space-y-2">
              {topAlerts.map((alert, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-danger shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-text-primary truncate">{alert.label}</p>
                    <p className="text-[11px] text-text-tertiary truncate">{alert.sub}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Bottom row – chart + activity                                       */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-4 animate-fade-up stagger-2">

        {/* Left – Findings Bar Chart */}
        <FindingsBarChart data={trend?.data ?? []} />

        {/* Right – Recent Activity */}
        <div className="rounded-xl border border-border bg-surface p-5">
          <p className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-4">
            Recent Activity
          </p>

          {activity.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-text-tertiary">
              <Activity className="h-7 w-7 mb-2" strokeWidth={1.5} />
              <p className="text-sm">No recent activity</p>
            </div>
          ) : (
            <ul className="space-y-3">
              {activity.map((item, i) => {
                const Icon = activityIcon(item.action ?? "");
                return (
                  <li key={item.id ?? i} className="flex items-start gap-3">
                    <span
                      className={cn(
                        "mt-1 h-2 w-2 rounded-full shrink-0",
                        activityDot(item.action ?? "")
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-primary leading-snug">
                        {formatActivityLabel(item)}
                      </p>
                      {item.created_at && (
                        <p className="text-xs text-text-tertiary mt-0.5">
                          {timeAgo(item.created_at)}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
