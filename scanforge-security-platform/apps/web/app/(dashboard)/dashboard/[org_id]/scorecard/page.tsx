"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertTriangle, CheckCircle, Shield } from "lucide-react";

import { api } from "@/lib/api";
import { PageHeader } from "@/components/scanforge/page-header";
import { ScorecardRing } from "@/components/scanforge/scorecard-ring";
import { Badge } from "@/components/ui/badge";
import { PageStatePanel } from "@/components/scanforge/page-state-panel";
import { derivePageState } from "@/lib/page-surface/page-state";

export default function ScorecardDashboardPage() {
  const { org_id } = useParams<{ org_id: string }>();
  const [projects, setProjects] = useState<any[]>([]);
  const [scorecards, setScorecards] = useState<Record<string, any>>({});
  const [failedProjectIds, setFailedProjectIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!org_id) return;
    api.projects.list(org_id, 0, 100)
      .then(async (res) => {
        const projectList = res.items ?? [];
        setProjects(projectList);
        const cards: Record<string, any> = {};
        const failed: string[] = [];
        await Promise.allSettled(
          projectList.map((project: any) =>
            api.scorecard.get(org_id, project.id)
              .then((scorecard: any) => {
                cards[project.id] = scorecard;
              })
              .catch(() => {
                failed.push(project.id);
              })
          )
        );
        setScorecards(cards);
        setFailedProjectIds(failed);
        setLoading(false);
      })
      .catch((err) => {
        setError(err?.message ?? "Failed to load projects");
        setLoading(false);
      });
  }, [org_id]);

  const pageState = derivePageState({
    loading,
    error,
    itemCount: projects.length,
  });

  const availableCount = Object.keys(scorecards).length;
  const unavailableCount = failedProjectIds.length;
  const avgScore = availableCount
    ? Math.round(
        Object.values(scorecards).reduce((sum: number, scorecard: any) => sum + (scorecard.overall_score || 0), 0) /
        availableCount
      )
    : null;

  return (
    <div>
      <PageHeader
        eyebrow="Governance"
        title="Security Scorecard"
        description="Review organization-wide security posture and compare project health side by side."
      />

      {pageState.kind === "loading" ? (
        <PageStatePanel state="loading" />
      ) : pageState.kind === "error" ? (
        <PageStatePanel state="error" message={pageState.message} retry={() => { setLoading(true); setError(null); }} />
      ) : (
        <>
          {avgScore !== null ? (
            <div className="mb-8 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="card-serif flex items-center gap-5 p-6">
                <ScorecardRing
                  grade={avgScore >= 90 ? "A" : avgScore >= 80 ? "B" : avgScore >= 70 ? "C" : avgScore >= 60 ? "D" : "F"}
                  overallScore={avgScore}
                />
                <div>
                  <p className="section-title mb-3">Organization Average</p>
                  <p className="text-sm leading-relaxed text-text-secondary">
                    Averaged across {availableCount} project{availableCount !== 1 ? "s" : ""}
                    {unavailableCount ? ` with ${unavailableCount} unavailable` : ""}.
                  </p>
                </div>
              </div>
              <div className="card-serif p-6">
                <p className="section-title mb-3">Interpretation</p>
                <p className="text-sm leading-relaxed text-text-secondary">
                  Use this view to identify which projects need immediate remediation focus, where fixes are landing, and where critical exposure is accumulating faster than it is being closed.
                </p>
              </div>
            </div>
          ) : null}

          {unavailableCount > 0 ? (
            <div className="mb-6 rounded-[10px] border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-secondary">
              {unavailableCount} project scorecard{unavailableCount !== 1 ? "s are" : " is"} unavailable and excluded from the organization average.
            </div>
          ) : null}

          <div>
            <div className="mb-3 flex items-center justify-between">
              <p className="section-title">Project Scorecards</p>
              <Badge variant="outline">{projects.length} projects</Badge>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {projects.map((project) => {
                const scorecard = scorecards[project.id];
                return (
                  <Link
                    key={project.id}
                    href={`/dashboard/${org_id}/projects/${project.id}`}
                    className="card-serif card-interactive block p-5"
                  >
                    <div className="mb-4 flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-border bg-background text-primary">
                        <Shield className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-text-primary">{project.name}</p>
                        <p className="mt-1 text-xs text-text-tertiary">{project.slug}</p>
                      </div>
                    </div>
                    {scorecard ? (
                      <>
                        <div className="mb-4 flex items-center justify-between">
                          <Badge variant="outline">{scorecard.grade}</Badge>
                          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
                            score {scorecard.overall_score}
                          </span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-background">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${scorecard.overall_score}%` }} />
                        </div>
                        <div className="mt-4 flex items-center gap-4 text-xs">
                          <span className="inline-flex items-center gap-1 text-danger">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            {scorecard.open_critical ?? 0} critical
                          </span>
                          <span className="inline-flex items-center gap-1 text-success">
                            <CheckCircle className="h-3.5 w-3.5" />
                            {scorecard.fixed_30d ?? 0} fixed
                          </span>
                        </div>
                      </>
                    ) : (
                      <p className="text-sm text-text-tertiary">Scorecard unavailable</p>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
