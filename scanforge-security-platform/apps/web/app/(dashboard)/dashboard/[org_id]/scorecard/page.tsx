"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Shield, TrendingUp, AlertTriangle, CheckCircle } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/scanforge/page-header";
import { ScorecardRing } from "@/components/scanforge/scorecard-ring";
import { StatCard } from "@/components/scanforge/stat-card";
import Link from "next/link";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";

export default function ScorecardDashboardPage() {
  const { org_id } = useParams<{ org_id: string }>();
  const [projects, setProjects] = useState<any[]>([]);
  const [scorecards, setScorecards] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org_id) return;
    api.projects.list(org_id as string, 0, 100).then(async (res) => {
      const projs = res.items ?? [];
      setProjects(projs);
      const cards: Record<string, any> = {};
      await Promise.allSettled(
        projs.map((p: any) =>
          api.scorecard.get(org_id as string, p.id).then((sc: any) => { cards[p.id] = sc; }).catch(() => {})
        )
      );
      setScorecards(cards);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [org_id]);

  const avgScore = scorecards && Object.keys(scorecards).length > 0
    ? Math.round(
        Object.values(scorecards).reduce((sum: number, sc: any) => sum + (sc.overall_score || 0), 0) /
        Object.keys(scorecards).length
      )
    : null;

  const gradeColor = (grade: string) => {
    const g = grade?.[0] ?? "";
    if (["A", "A+"].includes(g)) return "var(--green)";
    if (g === "B") return "#22c55e";
    if (g === "C") return "var(--amber)";
    if (g === "D") return "#fb923c";
    return "var(--red)";
  };

  return (
    <div>
      <PageHeader
        title="Security Scorecard"
        description="Organization-wide security posture overview"
      />

      {avgScore !== null && (
        <div className="flex items-center gap-6 mb-8 animate-fade-up">
          <ScorecardRing
            grade={avgScore >= 90 ? "A" : avgScore >= 80 ? "B" : avgScore >= 70 ? "C" : avgScore >= 60 ? "D" : "F"}
            overallScore={avgScore}
          />
          <div>
            <h2 className="font-display text-lg text-text-primary">Organization Security Score</h2>
            <p className="text-text-secondary text-sm">
              Average across {Object.keys(scorecards).length} project{Object.keys(scorecards).length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <SkeletonCards count={3} />
      ) : (
        <>
          <h3 className="font-display text-lg text-text-primary mb-4">Project Scorecards</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((proj) => {
              const sc = scorecards[proj.id];
              return (
                <Link key={proj.id} href={`/dashboard/${org_id}/projects/${proj.id}`}
                  className={cn(
                    "block rounded-lg border border-border bg-surface p-4 transition-colors hover:bg-surface-hover",
                    "animate-fade-up"
                  )}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <Shield size={16} className="text-text-secondary" />
                    <span className="text-text-primary font-medium text-sm">{proj.name}</span>
                  </div>
                  {sc ? (
                    <>
                      <div
                        className="inline-block mb-3 px-2.5 py-0.5 rounded-md border text-sm font-mono font-medium"
                        style={{ color: gradeColor(sc.grade), borderColor: gradeColor(sc.grade) }}
                      >
                        {sc.grade}
                      </div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-text-secondary text-xs">Overall</span>
                        <div className="flex-1 h-1.5 bg-background rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full transition-all"
                            style={{ width: `${sc.overall_score}%` }}
                          />
                        </div>
                        <span className="text-text-primary text-xs font-mono">{sc.overall_score}</span>
                      </div>
                      <div className="flex items-center gap-4 mt-3">
                        <span className="flex items-center gap-1 text-danger text-xs">
                          <AlertTriangle size={12} /> {sc.critical_count ?? 0}
                        </span>
                        <span className="flex items-center gap-1 text-success text-xs">
                          <CheckCircle size={12} /> {sc.fixed_30d ?? 0} fixed
                        </span>
                      </div>
                    </>
                  ) : (
                    <p className="text-text-tertiary text-sm">No scan data</p>
                  )}
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
