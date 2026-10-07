"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Plus, Search, Settings } from "lucide-react";

import { api } from "@/lib/api";
import { getSlugAdjustmentNotice, getSlugPreviewMessage } from "@/lib/organizations/slug-feedback";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";
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
        title="Organizations"
        description="The organizations you can open. Each one holds projects and the findings inside them."
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            New organization
          </Button>
        }
      />

      {createNotice ? (
        <div className="mb-6 rounded-[10px] border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-text-primary">
          {createNotice}
        </div>
      ) : null}

      {orgs.length > 0 ? (
        <div className="mb-6">
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
            <DialogTitle>New organization</DialogTitle>
            <DialogDescription>A name and a slug. The slug is the URL.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">Name</Label>
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
          description="Try a different search term."
        />
      ) : filteredOrgs.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No organizations yet"
          description="Create an organization, then add a project and a repository."
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              New organization
            </Button>
          }
        />
      ) : (
        <ul className="divide-y divide-border border-y border-border">
          {filteredOrgs.map((org) => {
            const stats = orgStats[org.id];
            const open = stats?.open_findings;

            return (
              <li key={org.id}>
                <Link
                  href={`/dashboard/${org.id}`}
                  className="flex items-baseline justify-between gap-4 py-3 hover-fine:bg-surface"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm text-text-primary">{org.name}</span>
                    <span className="block truncate text-xs text-text-tertiary">{org.slug}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    <span className={open > 0 ? "font-mono text-sm text-primary" : "font-mono text-sm text-text-tertiary"}>
                      {stats === undefined ? "" : open ?? "—"}
                    </span>
                    <button
                      type="button"
                      aria-label={`Settings for ${org.name}`}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        router.push(`/dashboard/${org.id}/settings`);
                      }}
                      className="text-text-tertiary hover-fine:text-text-primary"
                    >
                      <Settings className="h-4 w-4" />
                    </button>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
