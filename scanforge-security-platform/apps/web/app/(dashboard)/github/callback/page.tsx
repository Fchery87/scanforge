"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { api } from "@/lib/api";
import { deriveCallbackState } from "@/lib/onboarding/next-step";
import { ScanForgeLogo } from "@/components/scanforge/logo";
import { Button } from "@/components/ui/button";

function CallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const ran = useRef(false);
  const [recoveryState, setRecoveryState] = useState<ReturnType<typeof deriveCallbackState> | null>(null);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const installationId = searchParams.get("installation_id");
    const orgId = localStorage.getItem("github_connect_org_id");

    const state = deriveCallbackState({
      installation_id: installationId,
      storedOrgId: orgId,
    });

    if (state.kind !== "success") {
      setRecoveryState(state);
      return;
    }

    localStorage.removeItem("github_connect_org_id");

    api.github.connect(state.orgId, { installation_id: installationId! })
      .then(() => {
        router.replace(`/dashboard/${state.orgId}/onboarding?org_id=${state.orgId}&github_connected=true`);
      })
      .catch(() => {
        setRecoveryState({ kind: "connect-failed" });
      });
  }, [searchParams, router]);

  if (recoveryState?.kind === "missing-install-id") {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
        <div className="card-serif w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-6 w-6" />
          </div>
          <p className="section-title mb-3">Integration</p>
          <h1 className="font-display text-[2.4rem] leading-none tracking-[-0.05em] text-text-primary">Connection Incomplete</h1>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            GitHub did not return an installation ID. This can happen if the installation was cancelled or denied.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link href="/dashboard">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
            <Link href="/dashboard?tab=settings">
              <Button>Try Again</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (recoveryState?.kind === "missing-org-context") {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
        <div className="card-serif w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-6 w-6" />
          </div>
          <p className="section-title mb-3">Integration</p>
          <h1 className="font-display text-[2.4rem] leading-none tracking-[-0.05em] text-text-primary">Session Expired</h1>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            The organization context was lost. This can happen if the page was refreshed or the session timed out during the GitHub flow.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link href="/dashboard">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
            <Link href="/onboarding">
              <Button>Restart Onboarding</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (recoveryState?.kind === "connect-failed") {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
        <div className="card-serif w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-6 w-6" />
          </div>
          <p className="section-title mb-3">Integration</p>
          <h1 className="font-display text-[2.4rem] leading-none tracking-[-0.05em] text-text-primary">Connection Failed</h1>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            We received the GitHub installation but could not link it to your organization. Please try again or contact support if the issue persists.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link href="/dashboard">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
            <Link href="/dashboard?tab=settings">
              <Button>Retry Connection</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
      <div className="card-serif w-full max-w-lg p-8 text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
          <ScanForgeLogo className="h-6 w-6" />
        </div>
        <p className="section-title mb-3">Integration</p>
        <h1 className="font-display text-[2.4rem] leading-none tracking-[-0.05em] text-text-primary">Connecting GitHub</h1>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          Finalizing the GitHub installation and returning you to organization settings.
        </p>
      </div>
    </main>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense fallback={<div />}>
      <CallbackContent />
    </Suspense>
  );
}
