"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import { ScanForgeLogo } from "@/components/scanforge/logo";

function CallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const installationId = searchParams.get("installation_id");
    const orgId = localStorage.getItem("github_connect_org_id");

    if (!installationId || !orgId) {
      router.replace("/dashboard");
      return;
    }

    localStorage.removeItem("github_connect_org_id");

    api.github.connect(orgId, { installation_id: installationId })
      .then(() => {
        router.replace(`/dashboard/${orgId}/settings?github_connected=true`);
      })
      .catch(() => {
        router.replace(`/dashboard/${orgId}/settings?github_error=true`);
      });
  }, [searchParams, router]);

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
