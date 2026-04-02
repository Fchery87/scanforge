"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Clock,
  Folder,
  Plus,
  Settings,
  Users,
  Zap,
} from "lucide-react";

import { api } from "@/lib/api";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonStats } from "@/components/scanforge/loading-skeleton";
import { StatCard } from "@/components/scanforge/stat-card";
import { PageStatePanel } from "@/components/scanforge/page-state-panel";
import { derivePageState } from "@/lib/page-surface/page-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function OrganizationPage() {
  const { org_id } = useParams();
  const [org, setOrg] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [activity, setActivity] = useState<any[]>([]);
  const [memberCount, setMemberCount] = useState(0);
  const [statsUnavailable, setStatsUnavailable] = useState(false);
  const [activityUnavailable, setActivityUnavailable] = useState(false);
  const [membersUnavailable, setMembersUnavailable] = useState(false);

  useEffect(() => {
    if (!org_id) return;
    Promise.allSettled([
      api.organizations.get(org_id as string),
      api.projects.list(org_id as string, 0, 50),
      api.organizations.stats(org_id as string),
      api.auditLogs.listOrg(org_id as string, 0, 10),
      api.members.list(org_id as string, 0, 1),
    ]).then((results) => {
      const [orgResult, projectsResult, statsResult, activityResult, membersResult] = results;

      if (orgResult.status !== "fulfilled" || projectsResult.status !== "fulfilled") {
        setLoading(false);
        return;
      }

      setOrg(orgResult.value);
      setProjects(projectsResult.value.items ?? []);

      if (statsResult.status === "fulfilled") {
        setStats(statsResult.value);
        setStatsUnavailable(false);
      } else {
        setStats(null);
        setStatsUnavailable(true);
      }

      if (activityResult.status === "fulfilled") {
        setActivity(activityResult.value.items ?? []);
        setActivityUnavailable(false);
      } else {
        setActivity([]);
        setActivityUnavailable(true);
      }

      if (membersResult.status === "fulfilled") {
        setMemberCount(membersResult.value.total ?? membersResult.value.items?.length ?? 0);
        setMembersUnavailable(false);
      } else {
        setMemberCount(0);
        setMembersUnavailable(true);
      }

      setLoading(false);
    }).catch(() => setLoading(false));
  }, [org_id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const project = await api.projects.create(org_id as string, form);
      setProjects((current) => [...current, project]);
      setShowCreate(false);
      setForm({ name: "", slug: "", description: "" });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  const pageState = derivePageState({
    loading,
    error: !org ? "Organization not found" : null,
    itemCount: projects.length,
  });

  if (pageState.kind === "loading") {
    return <PageStatePanel state="loading" />;
  }

  if (pageState.kind === "error") {
    return (
      <PageStatePanel
        state="error"
        message="This organization does not exist or you no longer have access to it."
        retry={() => { setLoading(true); }}
      />
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Organization"
        title={org.name}
        description="Review project coverage, monitoring activity, and operational signals across this workspace."
        actions={
          <>
            <Badge variant="outline" className="hidden rounded-[6px] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.12em] md:inline-flex">
              <Users className="h-3.5 w-3.5" />
              {membersUnavailable ? "Members unavailable" : `${memberCount} member${memberCount !== 1 ? "s" : ""}`}
            </Badge>
            {projects.length > 0 ? (
              <Link href={`/dashboard/${org_id}/projects`}>
                <Button variant="outline" size="sm">
                  <Zap className="h-3.5 w-3.5" />
                  Scan All
                </Button>
              </Link>
            ) : null}
            <Link href={`/dashboard/${org_id}/settings`}>
              <Button variant="outline" size="sm">
                <Settings className="h-3.5 w-3.5" />
                Settings
              </Button>
            </Link>
            <Button onClick={() => setShowCreate(true)} size="sm">
              <Plus className="h-4 w-4" />
              New Project
            </Button>
          </>
        }
      />

      <div className="mb-8 grid gap-4 lg:grid-cols-[1.35fr_0.95fr]">
        <div className="card-serif p-6">
          <p className="section-title mb-3">Workspace Identity</p>
          <div className="flex items-start gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated font-display text-[1.5rem] text-primary">
              {org.name?.charAt(0)}
            </div>
            <div className="min-w-0">
              <p className="font-display text-[1.6rem] leading-none tracking-[-0.03em] text-text-primary">
                {org.name}
              </p>
              <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.16em] text-text-tertiary">
                {org.slug}
              </p>
              <p className="mt-4 max-w-[56ch] text-sm leading-relaxed text-text-secondary">
                Use this workspace to group projects, monitor findings, and manage access for the teams responsible for remediation.
              </p>
            </div>
          </div>
        </div>

        <div className="card-serif p-6">
          <p className="section-title mb-3">Current Coverage</p>
          <div className="grid grid-cols-2 gap-3">
            <StatCard icon={Folder} value={projects.length} label="Projects" variant="primary" />
            <StatCard
              icon={Users}
              value={membersUnavailable ? "N/A" : memberCount}
              label="Members"
              variant="default"
            />
          </div>
        </div>
      </div>

      <div className="mb-8 grid gap-4 md:grid-cols-3">
        <StatCard
          icon={AlertCircle}
          value={statsUnavailable ? "Unavailable" : stats?.open_findings ?? 0}
          label={statsUnavailable ? "Findings Data" : "Open Findings"}
          variant="warning"
        />
        <StatCard
          icon={Activity}
          value={statsUnavailable ? "Unavailable" : stats?.scans_today ?? 0}
          label={statsUnavailable ? "Scans Data" : "Scans Today"}
          variant="success"
        />
        <StatCard
          icon={Clock}
          value={activityUnavailable ? "Unavailable" : activity.length}
          label={activityUnavailable ? "Activity Feed" : "Recent Events"}
          variant="default"
        />
      </div>

      {statsUnavailable || activityUnavailable || membersUnavailable ? (
        <div className="mb-6 rounded-[10px] border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-secondary">
          Some organization data is temporarily unavailable.
          {statsUnavailable ? " Workspace stats failed to load." : ""}
          {activityUnavailable ? " Recent activity failed to load." : ""}
          {membersUnavailable ? " Member count failed to load." : ""}
        </div>
      ) : null}

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Project</DialogTitle>
            <DialogDescription>Add a new security scanning project.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="proj-name">Project Name</Label>
              <Input
                id="proj-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Backend API"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="proj-slug">Slug</Label>
              <Input
                id="proj-slug"
                value={form.slug}
                onChange={(e) =>
                  setForm({
                    ...form,
                    slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
                  })
                }
                placeholder="e.g. backend-api"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="proj-desc">Description</Label>
              <Input
                id="proj-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Optional description"
              />
            </div>
            {createError ? (
              <div className="rounded-[10px] border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
                {createError}
              </div>
            ) : null}
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <p className="section-title">Projects</p>
            {projects.length > 0 ? (
              <Badge variant="outline" className="rounded-[6px] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.12em]">
                {projects.length} total
              </Badge>
            ) : null}
          </div>

          {projects.length === 0 ? (
            <EmptyState
              icon={Folder}
              title="No projects yet"
              description="Create your first project to start scanning repositories in this workspace."
              action={
                <Button onClick={() => setShowCreate(true)}>
                  <Plus className="h-4 w-4" />
                  Create Project
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {projects.map((project) => (
                <Link
                  key={project.id}
                  href={`/dashboard/${org_id}/projects/${project.id}`}
                  className="card-serif card-interactive group flex items-center gap-4 p-4"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-border bg-background text-secondary">
                    <Folder className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-text-primary">{project.name}</h3>
                    {project.description ? (
                      <p className="mt-1 truncate text-xs text-text-tertiary">{project.description}</p>
                    ) : (
                      <p className="mt-1 text-xs text-text-tertiary">No description provided.</p>
                    )}
                  </div>
                  <div className="hidden gap-2 md:flex">
                    <Badge variant="outline">{project.repo_count ?? 0} repos</Badge>
                    <Badge variant={(project.open_findings_count ?? 0) > 0 ? "warning" : "default"}>
                      {project.open_findings_count ?? 0} findings
                    </Badge>
                  </div>
                  <ArrowRight className="h-4 w-4 text-text-tertiary transition-transform duration-200 group-hover:translate-x-1 group-hover:text-primary" />
                </Link>
              ))}
            </div>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <p className="section-title">Recent Activity</p>
            <Link href={`/dashboard/${org_id}/audit-logs`} className="text-sm text-primary">
              View all
            </Link>
          </div>

          <div className="card-serif overflow-hidden">
            {activityUnavailable ? (
              <div className="px-4 py-8 text-sm text-text-tertiary">Recent activity unavailable.</div>
            ) : activity.length === 0 ? (
              <div className="px-4 py-8 text-sm text-text-tertiary">No activity recorded yet.</div>
            ) : (
              activity.map((log) => (
                <div key={log.id} className="flex items-start gap-3 border-b border-border/60 px-4 py-4 last:border-0">
                  <span className="mt-2 h-2 w-2 rounded-full bg-primary" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text-primary">
                      <span className="font-medium">{log.action}</span>
                      {log.target ? <span className="text-text-secondary"> on {log.target}</span> : null}
                    </p>
                    {log.actor_name ? (
                      <p className="mt-1 text-xs text-text-tertiary">by {log.actor_name}</p>
                    ) : null}
                  </div>
                  <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">
                    {new Date(log.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
