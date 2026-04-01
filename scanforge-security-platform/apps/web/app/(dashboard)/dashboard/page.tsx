"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Plus, Search, Settings } from "lucide-react";

import { api } from "@/lib/api";
import { getSlugAdjustmentNotice, getSlugPreviewMessage } from "@/lib/organizations/slug-feedback";
import { deriveRiskGrade } from "@/lib/scanforge-ui";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";
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

export default function OrganizationsPage() {
  const router = useRouter();
  const [orgs, setOrgs] = useState<any[]>([]);
  const [orgStats, setOrgStats] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "" });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [createNotice, setCreateNotice] = useState<string | null>(null);
  const [slugPreview, setSlugPreview] = useState<{ available_slug: string; adjusted: boolean } | null>(null);
  const [slugPreviewLoading, setSlugPreviewLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.organizations
      .list(0, 20)
      .then(async (res) => {
        const orgList = res.items ?? [];
        setOrgs(orgList);
        const statsMap: Record<string, any> = {};
        await Promise.allSettled(
          orgList.map((org) =>
            api.organizations.stats(org.id)
              .then((stats) => {
                statsMap[org.id] = stats;
              })
              .catch(() => {
                statsMap[org.id] = null;
              })
          )
        );
        setOrgStats(statsMap);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const filteredOrgs = orgs.filter((org) =>
    !search ||
    org.name.toLowerCase().includes(search.toLowerCase()) ||
    org.slug.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    if (!showCreate || !form.slug) {
      setSlugPreview(null);
      setSlugPreviewLoading(false);
      return;
    }

    let cancelled = false;
    setSlugPreviewLoading(true);

    const timeoutId = window.setTimeout(async () => {
      try {
        const preview = await api.organizations.previewSlug(form.slug);
        if (!cancelled) {
          setSlugPreview({
            available_slug: preview.available_slug,
            adjusted: preview.adjusted,
          });
        }
      } catch {
        if (!cancelled) {
          setSlugPreview(null);
        }
      } finally {
        if (!cancelled) {
          setSlugPreviewLoading(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [form.slug, showCreate]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError("");
    setCreateNotice(null);
    try {
      const requestedSlug = form.slug;
      const org = await api.organizations.create(form);
      setOrgs((current) => [...current, org]);
      setShowCreate(false);
      setForm({ name: "", slug: "" });
      setCreateNotice(getSlugAdjustmentNotice(requestedSlug, org.slug));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="Organizations"
        description="Manage the workspaces that hold projects, repositories, findings, and governance settings."
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            New Organization
          </Button>
        }
      />

      {createNotice ? (
        <div className="mb-6 rounded-[10px] border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-text-primary">
          {createNotice}
        </div>
      ) : null}

      {orgs.length > 0 ? (
        <div className="card-serif mb-6 p-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
            <Input
              placeholder="Search organizations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-11 bg-background pl-9"
            />
          </div>
        </div>
      ) : null}

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Organization</DialogTitle>
            <DialogDescription>Add a new team workspace.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">Organization Name</Label>
              <Input
                id="org-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Acme Security Team"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="org-slug">Slug</Label>
              <Input
                id="org-slug"
                value={form.slug}
                onChange={(e) => {
                  setError("");
                  setCreateNotice(null);
                  setSlugPreview(null);
                  setForm({
                    ...form,
                    slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
                  });
                }}
                placeholder="e.g. acme-security"
                required
              />
              {form.slug ? (
                <div
                  className={cn(
                    "rounded-[10px] border px-3 py-2 text-xs",
                    slugPreview?.adjusted
                      ? "border-warning/30 bg-warning/10 text-text-primary"
                      : "border-border bg-surface text-text-secondary"
                  )}
                >
                  {slugPreviewLoading
                    ? "Checking slug availability..."
                    : getSlugPreviewMessage(form.slug, slugPreview?.available_slug ?? form.slug)}
                </div>
              ) : null}
            </div>
            {error ? (
              <div className="rounded-[10px] border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">
                {error}
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

      {loading ? (
        <SkeletonCards count={4} />
      ) : filteredOrgs.length === 0 && search ? (
        <EmptyState
          icon={Building2}
          title="No organizations found"
          description="Try a different search term or create a new workspace."
        />
      ) : filteredOrgs.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No organizations yet"
          description="Create your first organization to start structuring projects and connecting repositories."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              Create Organization
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {filteredOrgs.map((org, index) => {
            const stats = orgStats[org.id];
            const grade = deriveRiskGrade(stats);

            return (
              <Link
                key={org.id}
                href={`/dashboard/${org.id}`}
                className="card-serif card-interactive animate-fade-up group relative flex min-h-[210px] flex-col justify-between p-6"
                style={{ animationDelay: `${index * 80}ms` }}
              >
                <div className="absolute inset-x-6 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="section-title mb-3">Organization</p>
                    <div className="mb-2 flex items-center gap-2">
                      <h2 className="truncate font-display text-[1.45rem] font-semibold tracking-[-0.03em] text-text-primary">
                        {org.name}
                      </h2>
                      {grade ? (
                        <span
                          className={cn(
                            "inline-flex h-7 min-w-[2rem] items-center justify-center rounded-[6px] border px-2 font-mono text-[11px] font-semibold uppercase tracking-[0.12em]",
                            grade.startsWith("A")
                              ? "border-success/30 bg-success/10 text-success"
                              : grade === "B"
                                ? "border-primary/30 bg-primary/10 text-primary"
                                : grade === "C"
                                  ? "border-warning/30 bg-warning/10 text-warning"
                                  : "border-danger/30 bg-danger/10 text-danger"
                          )}
                        >
                          {grade}
                        </span>
                      ) : null}
                    </div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-text-tertiary">
                      {org.slug}
                    </p>
                  </div>

                  <button
                    type="button"
                    aria-label={`Settings for ${org.name}`}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      router.push(`/dashboard/${org.id}/settings`);
                    }}
                    className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-border bg-background text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
                  >
                    <Settings className="h-4 w-4" />
                  </button>
                </div>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-[10px] border border-border bg-background px-4 py-3">
                      <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Projects</p>
                      <p className="mt-2 font-display text-[1.6rem] leading-none text-text-primary">
                        {stats?.project_count ?? 0}
                      </p>
                    </div>
                    <div className="rounded-[10px] border border-border bg-background px-4 py-3">
                      <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">Open Findings</p>
                      <p className="mt-2 font-display text-[1.6rem] leading-none text-text-primary">
                        {stats?.open_findings ?? 0}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between border-t border-border pt-4">
                    <Badge variant="outline" className="rounded-[6px] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.12em]">
                      <Building2 className="h-3.5 w-3.5" />
                      Workspace
                    </Badge>
                    <span className="text-sm font-medium text-primary">Open workspace</span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
