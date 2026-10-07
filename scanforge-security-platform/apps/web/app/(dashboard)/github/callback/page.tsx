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
    const stateParam = searchParams.get("state");

    const state = deriveCallbackState({
      installation_id: installationId,
      state: stateParam,
    });

    if (state.kind !== "success") {
      setRecoveryState(state);
      return;
    }

    api.github.installCallback(installationId!, stateParam!)
      .then(() => {
        router.replace(`/onboarding?github_connected=true`);
      })
      .catch(() => {
        setRecoveryState({ kind: "connect-failed" });
      });
  }, [searchParams, router]);

  if (recoveryState?.kind === "missing-install-id") {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">Connection incomplete</h1>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            GitHub did not return an installation. The install was cancelled, or it was denied.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link href="/dashboard">
              <Button variant="outline">Back to dashboard</Button>
            </Link>
            <Link href="/onboarding">
              <Button>Try again</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (recoveryState?.kind === "missing-state") {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">Session expired</h1>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            The GitHub callback is missing or expired. Start the connection again.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link href="/dashboard">
              <Button variant="outline">Back to dashboard</Button>
            </Link>
            <Link href="/onboarding">
              <Button>Restart onboarding</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (recoveryState?.kind === "connect-failed") {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
        <div className="w-full max-w-lg p-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
            <ScanForgeLogo className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">Connection failed</h1>
          <p className="mt-4 text-sm leading-relaxed text-text-secondary">
            GitHub sent the installation, but it could not be linked to this organization.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link href="/dashboard">
              <Button variant="outline">Back to dashboard</Button>
            </Link>
            <Link href="/onboarding">
              <Button>Try again</Button>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-6 py-12">
      <div className="w-full max-w-lg p-8 text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-[12px] border border-border bg-surface-elevated text-primary">
          <ScanForgeLogo className="h-6 w-6" />
        </div>
        <h1 className="text-2xl font-semibold text-text-primary">Connecting GitHub</h1>
        <p className="mt-4 text-sm leading-relaxed text-text-secondary">
          Linking the installation, then returning you to the dashboard.
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
