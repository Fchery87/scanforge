"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";
import { Plus, Folder, AlertCircle, Activity, ArrowRight, Settings, Users, Clock, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/scanforge/page-header";
import { StatCard } from "@/components/scanforge/stat-card";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonCards, SkeletonStats, SkeletonList } from "@/components/scanforge/loading-skeleton";
import { cn } from "@/lib/utils";

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
      const proj = await api.projects.create(org_id as string, form);
      setProjects([...projects, proj]);
      setShowCreate(false);
      setForm({ name: "", slug: "", description: "" });
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  if (loading) return <SkeletonStats count={3} />;
  if (!org) {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Organization not found"
        description="This organization doesn't exist or you don't have access."
        action={<Link href="/dashboard"><Button variant="outline">Go Back</Button></Link>}
      />
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8 animate-fade-up">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-white text-xl font-bold font-display shadow-lg shadow-primary/20">
            {org.name?.charAt(0)}
          </div>
          <div>
            <h1 className="text-2xl font-bold font-display tracking-tight">{org.name}</h1>
            <span className="text-xs text-text-tertiary font-mono">{org.slug}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-sm text-text-tertiary mr-2">
            <Users className="h-4 w-4" /> {membersUnavailable ? "Members unavailable" : `${memberCount} member${memberCount !== 1 ? "s" : ""}`}
          </span>
          {projects.length > 0 && (
            <Link href={`/dashboard/${org_id}/projects`}>
              <Button variant="outline" size="sm">
                <Zap className="h-3.5 w-3.5" /> Scan All
              </Button>
            </Link>
          )}
          <Link href={`/dashboard/${org_id}/settings`}>
            <Button variant="outline" size="sm">
              <Settings className="h-3.5 w-3.5" /> Settings
            </Button>
          </Link>
          <Button onClick={() => setShowCreate(true)} size="sm">
            <Plus className="h-4 w-4" /> New Project
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 mb-8 animate-fade-up stagger-1">
        <StatCard icon={Folder} value={projects.length} label="Projects" variant="primary" />
        <StatCard
          icon={AlertCircle}
          value={statsUnavailable ? "Unavailable" : stats?.open_findings ?? 0}
          label={statsUnavailable ? "Open Findings Data" : "Open Findings"}
          variant="warning"
        />
        <StatCard
          icon={Activity}
          value={statsUnavailable ? "Unavailable" : stats?.scans_today ?? 0}
          label={statsUnavailable ? "Scans Today Data" : "Scans Today"}
          variant="success"
        />
      </div>

      {(statsUnavailable || activityUnavailable || membersUnavailable) && (
        <div className="mb-6 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-text-secondary">
          Some dashboard data is temporarily unavailable.
          {statsUnavailable && " Organization stats failed to load."}
          {activityUnavailable && " Recent activity failed to load."}
          {membersUnavailable && " Member count failed to load."}
        </div>
      )}

      {/* Create Modal */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Project</DialogTitle>
            <DialogDescription>Add a new security scanning project</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="proj-name">Project Name</Label>
              <Input id="proj-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Backend API" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="proj-slug">Slug</Label>
              <Input id="proj-slug" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })} placeholder="e.g. backend-api" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="proj-desc">Description</Label>
              <Input id="proj-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional description" />
            </div>
            {createError && <div className="rounded-lg bg-danger/10 border border-danger/30 px-3 py-2 text-sm text-danger">{createError}</div>}
            <div className="flex gap-2 justify-end pt-1">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>{creating ? "Creating..." : "Create"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Projects Section */}
      <div className="mb-2">
        <h2 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Projects</h2>
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon={Folder}
          title="No projects yet"
          description="Create your first project to start scanning repositories"
          action={<Button onClick={() => setShowCreate(true)}><Plus className="h-4 w-4" /> Create Project</Button>}
        />
      ) : (
        <div className="space-y-2">
          {projects.map((proj) => (
            <Link
              key={proj.id}
              href={`/dashboard/${org_id}/projects/${proj.id}`}
              className="group flex items-center gap-4 rounded-lg border border-border bg-surface px-4 py-3.5 transition-all duration-200 hover:border-border-strong hover:bg-surface-hover"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/10 text-secondary flex-shrink-0">
                <Folder size={18} strokeWidth={1.5} />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-text-primary">{proj.name}</h3>
                {proj.description && <p className="text-xs text-text-tertiary truncate mt-0.5">{proj.description}</p>}
              </div>
              <div className="flex gap-1.5">
                <Badge variant="default">{proj.repo_count ?? 0} repos</Badge>
                <Badge variant={proj.open_findings_count > 0 ? "warning" : "default"}>
                  {proj.open_findings_count ?? 0} findings
                </Badge>
              </div>
              <ArrowRight className="h-4 w-4 text-text-tertiary flex-shrink-0 transition-transform duration-200 group-hover:translate-x-1 group-hover:text-primary" />
            </Link>
          ))}
        </div>
      )}

      {/* Activity */}
      {(activity.length > 0 || activityUnavailable) && (
        <div className="mt-10 animate-fade-up stagger-3">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider">Recent Activity</h2>
            <Link href={`/dashboard/${org_id}/audit-logs`} className="text-xs text-primary hover:underline font-medium">View all</Link>
          </div>
          <div className="rounded-xl border border-border bg-surface overflow-hidden">
            {activityUnavailable ? (
              <div className="px-4 py-8 text-sm text-text-tertiary">
                Recent activity unavailable.
              </div>
            ) : (
              activity.map((log) => (
                <div key={log.id} className="flex items-center gap-3 px-4 py-3 border-b border-border/50 last:border-0">
                  <div className="h-2 w-2 rounded-full bg-primary flex-shrink-0" />
                  <div className="flex-1 text-sm min-w-0">
                    <span className="font-medium text-text-primary">{log.action}</span>
                    {log.target && <span className="text-text-secondary"> on {log.target}</span>}
                    {log.actor_name && <span className="text-text-tertiary"> by {log.actor_name}</span>}
                  </div>
                  <span className="flex items-center gap-1 text-[11px] text-text-tertiary font-mono flex-shrink-0">
                    <Clock className="h-3 w-3" /> {new Date(log.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
