"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  FileSearch,
  FolderKanban,
  Github,
  GitBranch,
  Scan,
  Settings,
  Shield,
  Users,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { deriveOnboardingNextActions } from "@/lib/page-surface/contracts";
import { getSlugAdjustmentNotice, getSlugPreviewMessage } from "@/lib/organizations/slug-feedback";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface OnboardingStep {
  id: string;
  label: string;
  description: string;
  completed: boolean;
  action_url: string | null;
}

interface OnboardingChecklist {
  user_id: string;
  organization_id: string | null;
  steps: OnboardingStep[];
  completion_percentage: number;
  is_complete: boolean;
}

const STEP_ICONS: Record<string, React.ReactNode> = {
  create_org: <Building2 size={18} />,
  connect_github: <Github size={18} />,
  create_project: <FolderKanban size={18} />,
  connect_repo: <GitBranch size={18} />,
  run_first_scan: <Scan size={18} />,
  review_findings: <FileSearch size={18} />,
};

function ConnectGitHubButton({ orgId }: { orgId: string }) {
  const [loading, setLoading] = useState(false);

  async function handleConnect() {
    setLoading(true);
    try {
      const { url } = await api.github.getInstallUrl(orgId);
      window.location.href = url;
    } catch {
      setLoading(false);
    }
  }

  return (
    <Button onClick={handleConnect} disabled={loading} size="sm">
      {loading ? "Redirecting..." : "Connect GitHub"}
    </Button>
  );
}

function OnboardingContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const orgId = searchParams.get("org_id") ?? undefined;
  const [checklist, setChecklist] = useState<OnboardingChecklist | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [inlineOrgForm, setInlineOrgForm] = useState({ name: "", slug: "" });
  const [creatingOrg, setCreatingOrg] = useState(false);
  const [orgCreateError, setOrgCreateError] = useState("");
  const [slugPreview, setSlugPreview] = useState<{ available_slug: string; adjusted: boolean } | null>(null);
  const [slugPreviewLoading, setSlugPreviewLoading] = useState(false);
  const githubConnected = searchParams.get("github_connected") === "true";
  const slugAdjustedFrom = searchParams.get("slug_adjusted_from");
  const createdOrgSlug = searchParams.get("org_slug");
  const slugAdjustmentNotice =
    slugAdjustedFrom && createdOrgSlug
      ? getSlugAdjustmentNotice(slugAdjustedFrom, createdOrgSlug)
      : null;

  useEffect(() => {
    if (localStorage.getItem("scanforge_onboarding_dismissed") === "true") setDismissed(true);
  }, []);

  useEffect(() => {
    async function loadChecklist() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/onboarding?org_id=${orgId || ""}`, { credentials: "include" });
        if (res.ok) setChecklist(await res.json());
        else setChecklist(null);
      } catch {
        setChecklist(null);
      } finally {
        setLoading(false);
      }
    }
    loadChecklist();
  }, [orgId]);

  useEffect(() => {
    if (!inlineOrgForm.slug) {
      setSlugPreview(null);
      setSlugPreviewLoading(false);
      return;
    }

    let cancelled = false;
    setSlugPreviewLoading(true);
    const timeoutId = window.setTimeout(async () => {
      try {
        const preview = await api.organizations.previewSlug(inlineOrgForm.slug);
        if (!cancelled) setSlugPreview({ available_slug: preview.available_slug, adjusted: preview.adjusted });
      } catch {
        if (!cancelled) setSlugPreview(null);
      } finally {
        if (!cancelled) setSlugPreviewLoading(false);
      }
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [inlineOrgForm.slug]);

  function handleDismiss() {
    localStorage.setItem("scanforge_onboarding_dismissed", "true");
    setDismissed(true);
  }

  async function handleInlineOrgCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreatingOrg(true);
    setOrgCreateError("");
    try {
      const requestedSlug = inlineOrgForm.slug;
      const org = await api.organizations.create(inlineOrgForm);
      const params = new URLSearchParams({ org_id: org.id, org_slug: org.slug });
      if (requestedSlug !== org.slug) params.set("slug_adjusted_from", requestedSlug);
      router.push(`/dashboard/${org.id}/onboarding?${params.toString()}`);
    } catch (error: any) {
      setOrgCreateError(error?.message ?? "Failed to create organization");
      setCreatingOrg(false);
    }
  }

  if (dismissed) return null;

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="ml-3 text-text-secondary">Loading checklist…</span>
        </div>
      </div>
    );
  }

  const completedCount = checklist?.steps.filter((step) => step.completed).length ?? 0;
  const totalCount = checklist?.steps.length ?? 6;
  const percentage = checklist?.completion_percentage ?? 0;
  const nextActions = deriveOnboardingNextActions(checklist?.steps ?? []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-8 flex items-start justify-between gap-6">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <Shield size={26} />
          </div>
          <div>
            <p className="section-title mb-2">Onboarding</p>
            <h1 className="font-display text-[2.2rem] leading-none tracking-[-0.04em] text-text-primary">Welcome to ScanForge</h1>
            <p className="mt-3 max-w-[52ch] text-sm leading-relaxed text-text-secondary">
              Complete the setup steps below to connect your workspace, onboard repositories, and get to your first findings review.
            </p>
          </div>
        </div>
        <button
          className="flex h-10 w-10 items-center justify-center rounded-[10px] border border-border bg-surface text-text-tertiary transition-colors hover:text-text-primary"
          onClick={handleDismiss}
          title="Dismiss"
        >
          <X size={16} />
        </button>
      </div>

      <div className="card-serif mb-6 p-6">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-text-primary">Progress</span>
          <span className="text-sm text-text-secondary">{completedCount} / {totalCount} completed</span>
        </div>
        <Progress value={percentage} className="h-2" />
        <p className="mt-2 text-right font-mono text-[11px] uppercase tracking-[0.12em] text-text-tertiary">{percentage}% complete</p>
      </div>

      {githubConnected ? (
        <div className="mb-6 rounded-[10px] border border-success/20 bg-success/10 px-4 py-3 text-sm text-text-primary">
          GitHub connected successfully.
        </div>
      ) : null}

      {slugAdjustmentNotice ? (
        <div className="mb-6 rounded-[10px] border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-text-primary">
          {slugAdjustmentNotice}
        </div>
      ) : null}

      <div className="space-y-3">
        {(checklist?.steps ?? []).map((step) => (
          <div
            key={step.id}
            className={cn(
              "card-serif p-5 transition-colors",
              step.completed ? "border-success/25 bg-success/[0.04]" : "hover:bg-surface-elevated"
            )}
          >
            <div className="flex items-start gap-4">
              <div className={cn(
                "flex h-10 w-10 items-center justify-center rounded-[10px] border",
                step.completed ? "border-success/30 bg-success/10 text-success" : "border-border bg-background text-text-secondary"
              )}>
                {step.completed ? <CheckCircle2 size={18} /> : STEP_ICONS[step.id] ?? <Shield size={18} />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className={cn("text-sm font-medium", step.completed ? "text-text-secondary line-through" : "text-text-primary")}>
                      {step.label}
                    </h3>
                    <p className="mt-1 text-sm text-text-tertiary">{step.description}</p>
                  </div>
                  {step.completed ? (
                    <Badge variant="success">Complete</Badge>
                  ) : null}
                </div>

                {step.id === "create_org" && !step.completed ? (
                  <form onSubmit={handleInlineOrgCreate} className="mt-4 space-y-3">
                    <Input
                      placeholder="Organization name"
                      required
                      value={inlineOrgForm.name}
                      onChange={(e) => {
                        setOrgCreateError("");
                        setSlugPreview(null);
                        setInlineOrgForm({
                          ...inlineOrgForm,
                          name: e.target.value,
                          slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
                        });
                      }}
                      className="h-10"
                    />
                    {orgCreateError ? (
                      <div className="rounded-[10px] border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">
                        {orgCreateError}
                      </div>
                    ) : null}
                    {inlineOrgForm.slug ? (
                      <div className={cn(
                        "rounded-[10px] border px-3 py-2 text-xs",
                        slugPreview?.adjusted ? "border-warning/30 bg-warning/10 text-text-primary" : "border-border bg-background text-text-secondary"
                      )}>
                        {slugPreviewLoading
                          ? "Checking slug availability..."
                          : getSlugPreviewMessage(inlineOrgForm.slug, slugPreview?.available_slug ?? inlineOrgForm.slug)}
                      </div>
                    ) : null}
                    <div className="flex items-center gap-3">
                      <Button type="submit" disabled={creatingOrg} size="sm">
                        {creatingOrg ? "Creating..." : "Create"}
                      </Button>
                      {inlineOrgForm.slug ? (
                        <span className="text-xs text-text-tertiary">
                          Requested slug: <span className="font-mono text-text-secondary">{inlineOrgForm.slug}</span>
                        </span>
                      ) : null}
                    </div>
                  </form>
                ) : null}

                {step.id === "connect_github" && !step.completed && orgId ? (
                  <div className="mt-4">
                    <ConnectGitHubButton orgId={orgId} />
                  </div>
                ) : null}
              </div>

              {step.action_url && !step.completed && step.id !== "create_org" ? (
                <Link href={step.action_url} className="mt-1 inline-flex items-center gap-1 text-sm text-primary hover:underline">
                  Go <ArrowRight size={14} />
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between">
        <Link href="/dashboard" className="text-sm text-text-secondary hover:text-text-primary">
          Back to Dashboard
        </Link>
        {orgId ? (
          <Link href={`/dashboard/${orgId}`} className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
            Go to Organization <ArrowRight size={16} />
          </Link>
        ) : null}
      </div>

      {checklist?.is_complete ? (
        <div className="mt-10">
          <h3 className="mb-4 font-display text-lg text-text-primary">What’s Next?</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <Link href={`/dashboard/${orgId}/scorecard`} className="card-serif card-interactive flex items-start gap-3 p-4">
              <BarChart3 size={20} className="mt-0.5 shrink-0 text-primary" />
              <div>
                <strong className="block text-sm text-text-primary">Security Scorecard</strong>
                <span className="text-xs text-text-tertiary">Review your organization’s security posture.</span>
              </div>
            </Link>
            <Link href={`/dashboard/${orgId}/settings`} className="card-serif card-interactive flex items-start gap-3 p-4">
              <Users size={20} className="mt-0.5 shrink-0 text-primary" />
              <div>
                <strong className="block text-sm text-text-primary">Invite Team Members</strong>
                <span className="text-xs text-text-tertiary">Add collaborators to your organization.</span>
              </div>
            </Link>
            <Link href={`/dashboard/${orgId}/audit-logs`} className="card-serif card-interactive flex items-start gap-3 p-4">
              <FileSearch size={20} className="mt-0.5 shrink-0 text-primary" />
              <div>
                <strong className="block text-sm text-text-primary">Audit Logs</strong>
                <span className="text-xs text-text-tertiary">Track all activity in your organization.</span>
              </div>
            </Link>
            <Link href={`/dashboard/${orgId}/settings`} className="card-serif card-interactive flex items-start gap-3 p-4">
              <Settings size={20} className="mt-0.5 shrink-0 text-primary" />
              <div>
                <strong className="block text-sm text-text-primary">Configure Notifications</strong>
                <span className="text-xs text-text-tertiary">Set up alerts and team access patterns.</span>
              </div>
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div />}>
      <OnboardingContent />
    </Suspense>
  );
}
