"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AlertCircle, Github, Plus, Save, Settings, Shield, Trash2, Users } from "lucide-react";

import { api } from "@/lib/api";
import { normalizeGithubIntegrationState, type GithubIntegrationState } from "@/lib/page-surface/contracts";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

function OrgSettingsContent() {
  const { org_id } = useParams();
  const searchParams = useSearchParams();
  const [org, setOrg] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ name: "", slug: "" });
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: "", role: "developer" });
  const [inviteError, setInviteError] = useState("");
  const [members, setMembers] = useState<any[]>([]);
  const [githubIntegration, setGithubIntegration] = useState<GithubIntegrationState>({ status: "disconnected" });
  const [githubLoading, setGithubLoading] = useState(true);
  const [githubMessage, setGithubMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (searchParams.get("github_connected") === "true") {
      setGithubMessage({ type: "success", text: "GitHub connected successfully." });
    } else if (searchParams.get("github_error") === "true") {
      setGithubMessage({ type: "error", text: "Failed to connect GitHub. Please try again." });
    }
  }, [searchParams]);

  useEffect(() => {
    if (org_id) {
      api.members.list(org_id as string).then((res: any) => setMembers(res.items || []));
    }
  }, [org_id]);

  useEffect(() => {
    if (!org_id) return;
    api.github.getIntegration(org_id as string)
      .then((data) => {
        setGithubIntegration(normalizeGithubIntegrationState(data));
        setGithubLoading(false);
      })
      .catch(() => setGithubLoading(false));
  }, [org_id]);

  useEffect(() => {
    if (!org_id) return;
    api.organizations.get(org_id as string)
      .then((data) => {
        setOrg(data);
        setForm({ name: data.name, slug: data.slug });
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError("");
    try {
      const updated = await api.organizations.update(org_id as string, form);
      setOrg(updated);
      setForm({ name: updated.name, slug: updated.slug });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save organization");
    } finally {
      setSaving(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteError("");
    try {
      await api.members.invite(org_id as string, inviteForm);
      setShowInvite(false);
      setInviteForm({ email: "", role: "developer" });
      const res = await api.members.list(org_id as string);
      setMembers(res.items || []);
    } catch (err: any) {
      setInviteError(err.message || "Failed to invite member");
    }
  }

  async function handleRoleChange(userId: string, newRole: string) {
    try {
      await api.members.updateRole(org_id as string, userId, newRole);
      setMembers((prev) => prev.map((member) => member.user_id === userId ? { ...member, role: newRole } : member));
    } catch {}
  }

  async function handleRemoveMember(userId: string) {
    if (!confirm("Remove this member? They will lose access to all projects.")) return;
    try {
      await api.members.remove(org_id as string, userId);
      setMembers((prev) => prev.filter((member) => member.user_id !== userId));
    } catch {}
  }

  async function handleConnectGitHub() {
    try {
      const { url } = await api.github.getInstallUrl(org_id as string);
      localStorage.setItem("github_connect_org_id", org_id as string);
      window.location.href = url;
    } catch {}
  }

  async function handleDisconnectGitHub() {
    if (!confirm("Disconnect GitHub? This will not remove connected repositories but new repos cannot be added.")) return;
    try {
      await api.github.disconnect(org_id as string);
      setGithubIntegration({ status: "disconnected" });
    } catch {}
  }

  async function handleDeleteOrg() {
    if (!org) return;
    const confirmValue = prompt(`Type "${org.slug}" to confirm permanent deletion:`);
    if (confirmValue !== org.slug) return;
    try {
      await api.organizations.delete(org_id as string);
      window.location.href = "/dashboard";
    } catch (err: any) {
      alert(err.message || "Failed to delete organization");
    }
  }

  if (loading) return <SkeletonTable rows={5} />;

  return (
    <div>
      <PageHeader
        eyebrow="Governance"
        title="Settings"
        description="Manage organization identity, integrations, access, and destructive actions."
      />

      <div className="space-y-6">
        <section className="card-serif p-6">
          <div className="mb-4 flex items-center gap-2">
            <Settings className="h-5 w-5 text-text-secondary" />
            <h2 className="text-lg font-semibold font-display text-text-primary">General</h2>
          </div>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">Organization Name</Label>
              <Input id="org-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="org-slug">Slug</Label>
              <Input id="org-slug" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} />
            </div>
            {saveError ? <p className="text-sm text-danger">{saveError}</p> : null}
            <Button type="submit" disabled={saving}>
              {saved ? <><Save className="h-4 w-4" /> Saved</> : "Save Changes"}
            </Button>
          </form>
        </section>

        <section className="card-serif p-6" id="integrations">
          <div className="mb-4 flex items-center gap-2">
            <Github className="h-5 w-5 text-text-secondary" />
            <h2 className="text-lg font-semibold font-display text-text-primary">Integrations</h2>
          </div>
          {githubMessage ? (
            <p className={cn("mb-3 text-sm", githubMessage.type === "success" ? "text-success" : "text-danger")}>
              {githubMessage.text}
            </p>
          ) : null}
          {githubLoading ? (
            <p className="text-sm text-text-tertiary">Loading…</p>
          ) : githubIntegration.status === "connected" ? (
            <div className="flex items-center justify-between rounded-[10px] border border-border bg-background p-4">
              <div>
                <p className="text-sm font-medium text-text-primary">GitHub App</p>
                <p className="mt-1 text-sm text-text-tertiary">
                  Connected as <strong className="text-text-secondary">{githubIntegration.accountLogin ?? "unknown"}</strong>
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="success">Active</Badge>
                <Button variant="ghost" size="sm" className="text-danger hover:text-danger" onClick={handleDisconnectGitHub}>
                  Disconnect
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-[10px] border border-border bg-background p-4">
              <div>
                <p className="text-sm font-medium text-text-primary">GitHub App</p>
                <p className="mt-1 text-sm text-text-tertiary">Not connected</p>
              </div>
              <Button onClick={handleConnectGitHub}>Connect GitHub</Button>
            </div>
          )}
        </section>

        <section className="card-serif p-6">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-text-secondary" />
              <h2 className="text-lg font-semibold font-display text-text-primary">Members</h2>
            </div>
            <Button size="sm" onClick={() => setShowInvite(true)}>
              <Plus className="h-4 w-4" />
              Invite
            </Button>
          </div>
          <div className="space-y-2">
            {members.map((member: any) => (
              <div key={member.id} className="flex items-center justify-between rounded-[10px] border border-border bg-background px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                    {(member.user_name || member.user_email || "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{member.user_name || member.user_email}</p>
                    {member.user_email ? <p className="text-xs text-text-tertiary">{member.user_email}</p> : null}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Select value={member.role} onValueChange={(val) => handleRoleChange(member.user_id, val)}>
                    <SelectTrigger className="h-8 w-[180px] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="owner">Owner</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="security_reviewer">Security Reviewer</SelectItem>
                      <SelectItem value="developer">Developer</SelectItem>
                      <SelectItem value="viewer">Viewer</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-text-tertiary hover:text-danger" onClick={() => handleRemoveMember(member.user_id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="card-serif p-6">
          <div className="mb-4 flex items-center gap-2">
            <Shield className="h-5 w-5 text-text-secondary" />
            <h2 className="text-lg font-semibold font-display text-text-primary">Security</h2>
          </div>
          <div className="flex items-start gap-3 rounded-[10px] border border-border bg-background p-4">
            <AlertCircle className="mt-0.5 h-4 w-4 text-text-secondary" />
            <p className="text-sm text-text-secondary">
              This page only shows security configuration when the backend exposes it. Static provider and secret badges remain intentionally absent unless runtime data exists.
            </p>
          </div>
        </section>

        <section className="rounded-[12px] border border-danger/30 bg-danger/5 p-6">
          <div className="mb-3 flex items-center gap-2">
            <Shield className="h-5 w-5 text-danger" />
            <h2 className="text-lg font-semibold font-display text-danger">Danger Zone</h2>
          </div>
          <p className="mb-4 text-sm text-text-secondary">
            Permanently delete this organization and all of its projects, repositories, and findings. This action cannot be undone.
          </p>
          <Button variant="destructive" onClick={handleDeleteOrg}>Delete Organization</Button>
        </section>
      </div>

      <Dialog open={showInvite} onOpenChange={setShowInvite}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Member</DialogTitle>
            <DialogDescription>Send an invitation to join this organization.</DialogDescription>
          </DialogHeader>
          {inviteError ? <p className="text-sm text-danger">{inviteError}</p> : null}
          <form onSubmit={handleInvite} className="space-y-4">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                type="email"
                required
                value={inviteForm.email}
                onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                placeholder="user@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={inviteForm.role} onValueChange={(val) => setInviteForm({ ...inviteForm, role: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="security_reviewer">Security Reviewer</SelectItem>
                  <SelectItem value="developer">Developer</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setShowInvite(false)}>Cancel</Button>
              <Button type="submit">Send Invite</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function OrgSettingsPage() {
  return (
    <Suspense fallback={<SkeletonTable rows={5} />}>
      <OrgSettingsContent />
    </Suspense>
  );
}
