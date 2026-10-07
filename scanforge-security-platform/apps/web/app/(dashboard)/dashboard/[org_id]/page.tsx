"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, Folder, Plus } from "lucide-react";

import { api } from "@/lib/api";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { PageStatePanel } from "@/components/scanforge/page-state-panel";
import { derivePageState } from "@/lib/page-surface/page-state";
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
      api.auditLogs.listOrg(org_id as string, 0, 8),
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
      setCreateError(err instanceof Error ? err.message : "Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  const pageState = derivePageState({
    loading,
    error: !org ? "Organization not found" : null,
    itemCount: projects.length,
  });

  if (pageState.kind === "loading") return <PageStatePanel state="loading" />;
  if (pageState.kind === "error") {
    return (
      <PageStatePanel
        state="error"
        message="This organization does not exist or you no longer have access to it."
        retry={() => setLoading(true)}
      />
    );
  }

  const firstProject = projects[0];
  const openFindings = statsUnavailable ? null : stats?.open_findings ?? 0;

  return (
    <div>
      <PageHeader
        title={org.name}
        description="Open findings across this organization, then the project each one belongs to."
        actions={
          <Button onClick={() => setShowCreate(true)} size="sm">
            <Plus className="h-4 w-4" />
            New project
          </Button>
        }
      />

      <div className="mb-8 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-border bg-border sm:grid-cols-4">
        <InstrumentCell
          label="Open findings"
          value={openFindings === null ? "—" : openFindings}
          href={firstProject ? `/dashboard/${org_id}/projects/${firstProject.id}/findings` : undefined}
          emphasize
        />
        <InstrumentCell label="Projects" value={projects.length} />
        <InstrumentCell label="Scans today" value={statsUnavailable ? "—" : stats?.scans_today ?? 0} />
        <InstrumentCell label="People" value={membersUnavailable ? "—" : memberCount} />
      </div>

      {statsUnavailable || activityUnavailable || membersUnavailable ? (
        <p className="mb-6 text-sm text-text-secondary">
          Some numbers failed to load.
          {statsUnavailable ? " Findings and scans." : ""}
          {activityUnavailable ? " Recent activity." : ""}
          {membersUnavailable ? " People." : ""}
        </p>
      ) : null}

      <div className="grid gap-10 lg:grid-cols-[1.4fr_0.8fr]">
        <section>
          <h2 className="mb-3 text-sm text-text-tertiary">Projects</h2>
          {projects.length === 0 ? (
            <EmptyState
              icon={Folder}
              title="No projects yet"
              description="Create a project, then connect a repository so scans have somewhere to land."
              action={
                <Button onClick={() => setShowCreate(true)}>
                  <Plus className="h-4 w-4" />
                  Create project
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-border border-y border-border">
              {projects.map((project) => {
                const open = project.open_findings_count ?? 0;
                return (
                  <li key={project.id}>
                    <Link
                      href={`/dashboard/${org_id}/projects/${project.id}`}
                      className="flex items-baseline justify-between gap-4 py-3 hover-fine:bg-surface"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm text-text-primary">{project.name}</span>
                        <span className="block truncate text-xs text-text-tertiary">
                          {project.description || `${project.repo_count ?? 0} repositories`}
                        </span>
                      </span>
                      <span className={open > 0 ? "font-mono text-sm text-primary" : "font-mono text-sm text-text-tertiary"}>
                        {open}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-sm text-text-tertiary">Recent activity</h2>
            <Link href={`/dashboard/${org_id}/audit-logs`} className="text-sm text-text-secondary hover-fine:text-text-primary">
              All activity
            </Link>
          </div>
          {activityUnavailable ? (
            <p className="text-sm text-text-tertiary">Activity failed to load.</p>
          ) : activity.length === 0 ? (
            <p className="text-sm text-text-tertiary">Nothing recorded yet.</p>
          ) : (
            <ul className="divide-y divide-border border-y border-border">
              {activity.map((log) => (
                <li key={log.id} className="flex items-baseline justify-between gap-3 py-2.5">
                  <span className="min-w-0 truncate text-sm text-text-primary">
                    {log.action}
                    {log.target ? <span className="text-text-tertiary"> on {log.target}</span> : null}
                  </span>
                  <span className="shrink-0 font-mono text-xs text-text-tertiary">
                    {new Date(log.created_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New project</DialogTitle>
            <DialogDescription>A project holds the repositories you scan together.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <Field label="Name" id="proj-name">
              <Input id="proj-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </Field>
            <Field label="Slug" id="proj-slug">
              <Input
                id="proj-slug"
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })}
                required
              />
            </Field>
            <Field label="Description" id="proj-desc">
              <Input id="proj-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </Field>
            {createError ? <p className="text-sm text-primary">{createError}</p> : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>{creating ? "Creating" : "Create project"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InstrumentCell({
  label,
  value,
  href,
  emphasize,
}: {
  label: string;
  value: string | number;
  href?: string;
  emphasize?: boolean;
}) {
  const body = (
    <div className="bg-background px-4 py-4">
      <p className="text-xs text-text-tertiary">{label}</p>
      <p className={`mt-1 font-mono text-[1.7rem] leading-none tracking-[-0.03em] ${emphasize ? "text-primary" : "text-text-primary"}`}>
        {value}
      </p>
    </div>
  );
  return href ? <Link href={href}>{body}</Link> : body;
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}
