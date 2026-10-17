"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/scanforge/page-header";
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
  const totalOpenCritical = Object.values(scorecards).reduce(
    (sum: number, scorecard: any) => sum + (scorecard.open_critical ?? 0),
    0
  );
  const totalOpen = Object.values(scorecards).reduce(
    (sum: number, scorecard: any) => sum + (scorecard.open_total ?? 0),
    0
  );

  return (
    <div>
      <PageHeader
        title="Exposure summary"
        description="Unresolved findings and scanner coverage across projects in this organization."
      />

      {pageState.kind === "loading" ? (
        <PageStatePanel state="loading" />
      ) : pageState.kind === "error" ? (
        <PageStatePanel state="error" message={pageState.message} retry={() => { setLoading(true); setError(null); }} />
      ) : (
        <>
          {availableCount > 0 ? (
            <div className="mb-8 flex items-center gap-5">
              <div className="rounded-[10px] border border-border bg-surface px-4 py-3">
                <p className="text-xs text-text-tertiary">Unresolved findings</p>
                <p className="mt-1 font-mono text-2xl text-text-primary">{totalOpen}</p>
                <p className="mt-1 text-xs text-text-tertiary">
                  {totalOpenCritical} critical across {availableCount} project{availableCount !== 1 ? "s" : ""}
                  {unavailableCount ? `. ${unavailableCount} did not load.` : "."}
                </p>
              </div>
            </div>
          ) : null}

          {unavailableCount > 0 ? (
            <div className="mb-6 rounded-[10px] border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-secondary">
              {unavailableCount} project summary{unavailableCount !== 1 ? "ies" : ""} did not load.
            </div>
          ) : null}

          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm text-text-tertiary">Projects</h2>
              <Badge variant="outline">{projects.length} projects</Badge>
            </div>
            <ul className="divide-y divide-border border-y border-border">
              {projects.map((project) => {
                const scorecard = scorecards[project.id];
                return (
                  <li key={project.id}>
                    <Link
                      href={`/dashboard/${org_id}/projects/${project.id}`}
                      className="flex items-baseline justify-between gap-4 py-3 hover-fine:bg-surface"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm text-text-primary">{project.name}</span>
                        <span className="block truncate text-xs text-text-tertiary">
                          {scorecard
                            ? `${scorecard.open_critical ?? 0} critical · ${scorecard.fixed_30d ?? 0} fixed in 30 days`
                            : "Summary did not load"}
                        </span>
                      </span>
                      <span className="shrink-0 font-mono text-sm text-text-primary">
                        {scorecard ? `${scorecard.open_total ?? 0} open` : "—"}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
