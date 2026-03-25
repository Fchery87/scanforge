"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Link from "next/link";
import { Building2, Plus, Search, Lock, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonCards } from "@/components/scanforge/loading-skeleton";
import { cn } from "@/lib/utils";

function deriveGrade(stats: any) {
  if (!stats) return null;
  const penalty = (stats.critical_findings ?? 0) * 25 + (stats.open_findings ?? 0) * 3;
  const score = Math.max(0, 100 - penalty);
  if (score >= 95) return "A+";
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

function gradeBadgeColor(grade: string | null) {
  if (!grade) return "";
  if (grade.startsWith("A")) return "border-success/30 bg-success/10 text-success";
  if (grade === "B") return "border-primary/30 bg-primary/10 text-primary";
  if (grade === "C") return "border-warning/30 bg-warning/10 text-warning";
  if (grade === "D") return "border-severity-high/30 bg-severity-high/10 text-severity-high";
  return "border-danger/30 bg-danger/10 text-danger";
}

export default function OrganizationsPage() {
  const router = useRouter();
  const [orgs, setOrgs] = useState<any[]>([]);
  const [orgStats, setOrgStats] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "" });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.organizations.list(0, 20).then(async (res) => {
      const orgList = res.items ?? [];
      setOrgs(orgList);
      const statsMap: Record<string, any> = {};
      await Promise.allSettled(
        orgList.map((org) =>
          api.organizations.stats(org.id)
            .then((s) => { statsMap[org.id] = s; })
            .catch(() => { statsMap[org.id] = null; })
        )
      );
      setOrgStats(statsMap);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filteredOrgs = orgs.filter((org) =>
    !search || org.name.toLowerCase().includes(search.toLowerCase()) || org.slug.toLowerCase().includes(search.toLowerCase())
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      const org = await api.organizations.create(form);
      setOrgs([...orgs, org]);
      setShowCreate(false);
      setForm({ name: "", slug: "" });
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
        description="Manage your teams and workspaces"
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> New Organization
          </Button>
        }
      />

      {/* Search bar */}
      {orgs.length > 0 && (
        <div className="mb-6 relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-tertiary pointer-events-none" />
          <Input
            placeholder="Search organizations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {/* Create Modal */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Organization</DialogTitle>
            <DialogDescription>Add a new team workspace</DialogDescription>
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
                onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })}
                placeholder="e.g. acme-security"
                required
              />
            </div>
            {error && (
              <div className="rounded-lg bg-danger/10 border border-danger/20 px-3 py-2 text-sm text-danger">
                {error}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-1">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Content */}
      {loading ? (
        <SkeletonCards count={3} />
      ) : filteredOrgs.length === 0 && search ? (
        <EmptyState
          icon={Building2}
          title="No organizations found"
          description="Try a different search term"
        />
      ) : filteredOrgs.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No organizations yet"
          description="Create your first organization to get started"
          action={
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" /> Create Organization
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {filteredOrgs.map((org, index) => {
            const grade = deriveGrade(orgStats[org.id]);
            return (
              <Link
                key={org.id}
                href={`/dashboard/${org.id}`}
                className={cn(
                  "group relative flex items-center gap-4 rounded-xl border border-border bg-surface p-5 transition-all duration-200",
                  "hover:border-border-strong hover:bg-surface-hover",
                  "animate-fade-up"
                )}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Top accent line on hover */}
                <div className="absolute top-0 left-[15%] right-[15%] h-[1px] bg-gradient-to-r from-transparent via-primary/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

                {/* Lock icon */}
                <div className="h-11 w-11 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Lock className="text-primary h-5 w-5" />
                </div>

                {/* Org name + slug */}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-text-primary truncate">{org.name}</h3>
                  <span className="text-xs text-text-tertiary font-mono">{org.slug}</span>
                </div>

                {/* Grade badge */}
                {grade && (
                  <span className={cn(
                    "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-bold font-display flex-shrink-0",
                    gradeBadgeColor(grade)
                  )}>
                    {grade}
                  </span>
                )}

                {/* Settings button */}
                <button
                  type="button"
                  aria-label={`Settings for ${org.name}`}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    router.push(`/dashboard/${org.id}/settings`);
                  }}
                  className="h-8 w-8 rounded-lg flex items-center justify-center text-text-tertiary hover:bg-surface-hover hover:text-text-primary transition-colors flex-shrink-0"
                >
                  <Settings className="h-4 w-4" />
                </button>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
