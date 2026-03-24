"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  Shield,
  GitBranch,
  Scan,
  FileSearch,
  Calendar,
  Building2,
  FolderKanban,
  X,
  Settings,
  BarChart3,
  Users,
  Github,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/scanforge/page-header";
import { OnboardingStepCard } from "@/components/scanforge/onboarding-step";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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

function ConnectGitHubButton({ orgId }: { orgId: string }) {
  const [loading, setLoading] = useState(false);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const { url } = await api.github.getInstallUrl(orgId);
      window.location.href = url;
    } catch {
      setLoading(false);
    }
  };

  return (
    <Button onClick={handleConnect} disabled={loading} size="sm">
      {loading ? "Redirecting..." : "Connect GitHub"}
    </Button>
  );
}

const STEP_ICONS: Record<string, React.ReactNode> = {
  create_org: <Building2 size={20} />,
  connect_github: <Github size={20} />,
  create_project: <FolderKanban size={20} />,
  connect_repo: <GitBranch size={20} />,
  run_first_scan: <Scan size={20} />,
  review_findings: <FileSearch size={20} />,
  setup_schedule: <Calendar size={20} />,
};

function OnboardingContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const orgId = searchParams.get("org_id") ?? undefined;
  const [checklist, setChecklist] = useState<OnboardingChecklist | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [inlineOrgForm, setInlineOrgForm] = useState({ name: "", slug: "" });
  const [creatingOrg, setCreatingOrg] = useState(false);
  const githubConnected = searchParams.get("github_connected") === "true";

  useEffect(() => {
    if (localStorage.getItem("scanforge_onboarding_dismissed") === "true") {
      setDismissed(true);
    }
  }, []);

  useEffect(() => {
    async function loadChecklist() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/onboarding?org_id=${orgId || ""}`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          setChecklist(data);
        } else {
          setChecklist(null);
        }
      } catch {
        setChecklist(null);
      } finally {
        setLoading(false);
      }
    }
    loadChecklist();
  }, [orgId]);

  const handleDismiss = () => {
    localStorage.setItem("scanforge_onboarding_dismissed", "true");
    setDismissed(true);
  };

  const handleInlineOrgCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingOrg(true);
    try {
      const org = await api.organizations.create(inlineOrgForm);
      router.push(`/dashboard/${org.id}/onboarding?org_id=${org.id}`);
    } catch {
      setCreatingOrg(false);
    }
  };

  if (dismissed) return null;

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto py-8 px-4">
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <span className="ml-3 text-text-secondary">Loading checklist...</span>
        </div>
      </div>
    );
  }

  const completedCount = checklist?.steps.filter((s) => s.completed).length ?? 0;
  const totalCount = checklist?.steps.length ?? 6;
  const percentage = checklist?.completion_percentage ?? 0;

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <div className="flex items-start gap-4 mb-8 relative">
        <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
          <Shield size={32} className="text-primary" />
        </div>
        <div className="flex-1">
          <h1 className="font-display text-2xl text-text-primary">Welcome to ScanForge</h1>
          <p className="text-text-secondary mt-1">
            Get started by completing the steps below to secure your repositories.
          </p>
        </div>
        <button
          className="p-2 rounded-lg text-text-tertiary hover:text-text-secondary hover:bg-surface-hover transition-colors"
          onClick={handleDismiss}
          title="Dismiss"
        >
          <X size={16} />
        </button>
      </div>

      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-text-primary">Your Progress</span>
          <span className="text-sm text-text-secondary">
            {completedCount} / {totalCount} completed
          </span>
        </div>
        <Progress value={percentage} className="h-2" />
        <p className="text-xs text-text-tertiary mt-1 text-right">{percentage}% complete</p>
      </div>

      {checklist?.is_complete && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-success/10 border border-success/20 mb-6 animate-fade-up">
          <CheckCircle2 size={24} className="text-success flex-shrink-0" />
          <div className="text-sm">
            <strong className="text-text-primary">All done! </strong>
            <span className="text-text-secondary">You&apos;ve completed your onboarding. Keep scanning to stay secure.</span>
          </div>
        </div>
      )}

      {githubConnected && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-success/10 border border-success/20 mb-6 animate-fade-up">
          <CheckCircle2 size={20} className="text-success flex-shrink-0" />
          <span className="text-sm text-text-primary">GitHub connected successfully!</span>
        </div>
      )}

      <div className="space-y-3 mb-8">
        {(checklist?.steps ?? []).map((step) => (
          <div
            key={step.id}
            className={cn(
              "relative flex items-start gap-4 p-4 rounded-lg border transition-colors",
              step.completed
                ? "border-success/20 bg-success/5"
                : "border-border bg-surface hover:bg-surface-hover"
            )}
          >
            <div className={cn(
              "flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center",
              step.completed
                ? "bg-success/10 text-success"
                : "bg-surface-elevated text-text-secondary"
            )}>
              {step.completed ? (
                <CheckCircle2 size={20} />
              ) : (
                STEP_ICONS[step.id] || <Circle size={20} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className={cn(
                "font-medium text-sm",
                step.completed ? "text-text-secondary line-through" : "text-text-primary"
              )}>
                {step.label}
              </h3>
              <p className="text-text-tertiary text-sm mt-0.5">{step.description}</p>
              {step.id === "create_org" && !step.completed && (
                <form onSubmit={handleInlineOrgCreate} className="flex items-center gap-2 mt-3">
                  <Input
                    placeholder="Organization name"
                    required
                    value={inlineOrgForm.name}
                    onChange={(e) => setInlineOrgForm({ ...inlineOrgForm, name: e.target.value, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })}
                    className="h-9 text-sm"
                  />
                  <Button type="submit" disabled={creatingOrg} size="sm">
                    {creatingOrg ? "Creating..." : "Create"}
                  </Button>
                </form>
              )}
              {step.id === "connect_github" && !step.completed && orgId && (
                <div className="mt-3">
                  <ConnectGitHubButton orgId={orgId} />
                </div>
              )}
            </div>
            {step.action_url && !step.completed && step.id !== "create_org" && (
              <Link
                href={step.action_url}
                className="flex-shrink-0 flex items-center gap-1 text-sm text-primary hover:underline mt-1"
              >
                Go <ArrowRight size={14} />
              </Link>
            )}
            {step.completed && (
              <span className="flex-shrink-0 inline-block px-2 py-0.5 rounded-md text-xs font-medium bg-success/10 text-success">
                Complete
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          Back to Dashboard
        </Link>
        {orgId && (
          <Link
            href={`/dashboard/${orgId}`}
            className="flex items-center gap-1.5 text-sm text-primary hover:underline"
          >
            Go to Organization <ArrowRight size={16} />
          </Link>
        )}
      </div>

      {checklist?.is_complete && (
        <div className="mt-10">
          <h3 className="font-display text-lg text-text-primary mb-4">What&apos;s Next?</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Link
              href={`/dashboard/${orgId}/scorecard`}
              className="flex items-start gap-3 p-4 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors"
            >
              <BarChart3 size={20} className="text-primary flex-shrink-0 mt-0.5" />
              <div>
                <strong className="text-sm text-text-primary block">Security Scorecard</strong>
                <span className="text-xs text-text-tertiary">Review your organization&apos;s security posture</span>
              </div>
            </Link>
            <Link
              href={`/dashboard/${orgId}/settings`}
              className="flex items-start gap-3 p-4 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors"
            >
              <Users size={20} className="text-primary flex-shrink-0 mt-0.5" />
              <div>
                <strong className="text-sm text-text-primary block">Invite Team Members</strong>
                <span className="text-xs text-text-tertiary">Add collaborators to your organization</span>
              </div>
            </Link>
            <Link
              href={`/dashboard/${orgId}/audit-logs`}
              className="flex items-start gap-3 p-4 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors"
            >
              <FileSearch size={20} className="text-primary flex-shrink-0 mt-0.5" />
              <div>
                <strong className="text-sm text-text-primary block">Audit Logs</strong>
                <span className="text-xs text-text-tertiary">Track all activity in your organization</span>
              </div>
            </Link>
            <Link
              href={`/dashboard/${orgId}/settings`}
              className="flex items-start gap-3 p-4 rounded-lg border border-border bg-surface hover:bg-surface-hover transition-colors"
            >
              <Settings size={20} className="text-primary flex-shrink-0 mt-0.5" />
              <div>
                <strong className="text-sm text-text-primary block">Configure Notifications</strong>
                <span className="text-xs text-text-tertiary">Set up Slack and email alerts</span>
              </div>
            </Link>
          </div>
        </div>
      )}
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
