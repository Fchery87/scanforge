"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { AlertCircle, Settings, Users, Shield, Save, Trash2, Plus, Github } from "lucide-react";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
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
  const [githubIntegration, setGithubIntegration] = useState<any>(null);
  const [githubLoading, setGithubLoading] = useState(true);
  const [githubMessage, setGithubMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (searchParams.get("github_connected") === "true") {
      setGithubMessage({ type: "success", text: "GitHub connected successfully!" });
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
      .then((data) => { setGithubIntegration(data); setGithubLoading(false); })
      .catch((err) => {
        console.error("Failed to fetch GitHub integration:", err);
        setGithubLoading(false);
      });
  }, [org_id]);

  const handleConnectGitHub = async () => {
    try {
      const { url } = await api.github.getInstallUrl(org_id as string);
      localStorage.setItem("github_connect_org_id", org_id as string);
      window.location.href = url;
    } catch { }
  };

  const handleDisconnectGitHub = async () => {
    if (!confirm("Disconnect GitHub? This will not remove connected repositories but new repos cannot be added.")) return;
    try {
      await api.github.disconnect(org_id as string);
      setGithubIntegration(null);
    } catch { }
  };

  const handleInvite = async (e: React.FormEvent) => {
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
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api.members.updateRole(org_id as string, userId, newRole);
      setMembers((prev) => prev.map((m) => m.user_id === userId ? { ...m, role: newRole } : m));
    } catch (err) { console.error(err); }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!confirm("Remove this member? They will lose access to all projects.")) return;
    try {
      await api.members.remove(org_id as string, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    } catch (err) { console.error(err); }
  };

  const handleDeleteOrg = async () => {
    if (!org) return;
    const confirm_ = prompt(`Type "${org.slug}" to confirm permanent deletion:`);
    if (confirm_ !== org.slug) return;
    try {
      await api.organizations.delete(org_id as string);
      window.location.href = "/dashboard";
    } catch (err: any) {
      alert(err.message || "Failed to delete organization");
    }
  };

  useEffect(() => {
    if (!org_id) return;
    api.organizations.get(org_id as string)
      .then((data) => {
        setOrg(data);
        setForm({ name: data.name, slug: data.slug });
        setLoading(false);
      }).catch(() => setLoading(false));
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

  if (loading) return <SkeletonTable rows={5} />;

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Organization settings and configuration"
      />

      <div className="space-y-6">
        <div className="rounded-xl border border-border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4">
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
            {saveError && <p className="text-sm text-danger">{saveError}</p>}
            <Button type="submit" disabled={saving}>
              {saved ? <><Save className="h-4 w-4 mr-1" /> Saved</> : "Save Changes"}
            </Button>
          </form>
        </div>

        <div className="rounded-xl border border-border bg-surface p-6" id="integrations">
          <div className="flex items-center gap-2 mb-4">
            <Github className="h-5 w-5 text-text-secondary" />
            <h2 className="text-lg font-semibold font-display text-text-primary">Integrations</h2>
          </div>

          {githubMessage && (
            <p className={cn("text-sm mb-3", githubMessage.type === "success" ? "text-success" : "text-danger")}>
              {githubMessage.text}
            </p>
          )}

          {githubLoading ? (
            <p className="text-sm text-text-tertiary">Loading...</p>
          ) : githubIntegration ? (
            <div className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated p-4">
              <div>
                <span className="text-sm font-medium text-text-primary">GitHub App</span>
                <span className="block text-sm text-text-tertiary">
                  Connected as <strong className="text-text-secondary">{githubIntegration.account_login ?? "unknown"}</strong>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-success border-success/30 bg-success/10">Active</Badge>
                <Button variant="ghost" size="sm" className="text-danger hover:text-danger" onClick={handleDisconnectGitHub}>
                  Disconnect
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated p-4">
              <div>
                <span className="text-sm font-medium text-text-primary">GitHub App</span>
                <span className="block text-sm text-text-tertiary">Not connected</span>
              </div>
              <Button onClick={handleConnectGitHub}>Connect GitHub</Button>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border bg-surface p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-text-secondary" />
              <h2 className="text-lg font-semibold font-display text-text-primary">Members</h2>
            </div>
            <Button size="sm" onClick={() => setShowInvite(true)}>
              <Plus className="h-4 w-4 mr-1" /> Invite
            </Button>
          </div>
          <div className="space-y-2">
            {members.map((m: any) => (
              <div key={m.id} className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-semibold">
                    {(m.user_name || m.user_email || "?")[0].toUpperCase()}
                  </div>
                  <div>
                    <span className="text-sm font-medium text-text-primary">{m.user_name || m.user_email}</span>
                    {m.user_email && <span className="block text-xs text-text-tertiary">{m.user_email}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Select value={m.role} onValueChange={(val) => handleRoleChange(m.user_id, val)}>
                    <SelectTrigger className="w-[180px] h-8 text-xs">
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
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-text-tertiary hover:text-danger"
                    onClick={() => handleRemoveMember(m.user_id)}
                    title="Remove member"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <Dialog open={showInvite} onOpenChange={setShowInvite}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Invite Member</DialogTitle>
              <DialogDescription>Send an invitation to join this organization.</DialogDescription>
            </DialogHeader>
            {inviteError && <p className="text-sm text-danger">{inviteError}</p>}
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

        <div className="rounded-xl border border-border bg-surface p-6">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="h-5 w-5 text-text-secondary" />
            <h2 className="text-lg font-semibold font-display text-text-primary">Security</h2>
          </div>
          <div className="flex items-start gap-3 rounded-lg border border-border bg-surface-elevated p-4">
            <AlertCircle className="h-4 w-4 text-text-secondary mt-0.5" />
            <p className="text-sm text-text-secondary">
              This page only shows security configuration when the backend exposes it. Static provider and secret
              badges were removed so the UI does not imply runtime state it cannot verify.
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-danger/30 bg-danger/5 p-6">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="h-5 w-5 text-danger" />
            <h2 className="text-lg font-semibold font-display text-danger">Danger Zone</h2>
          </div>
          <p className="text-sm text-text-secondary mb-4">
            Permanently delete this organization and all its projects, repositories, and findings. This action cannot be undone.
          </p>
          <Button variant="destructive" onClick={handleDeleteOrg}>
            Delete Organization
          </Button>
        </div>
      </div>
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
