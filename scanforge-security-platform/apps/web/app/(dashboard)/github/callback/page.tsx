"use client";

import { useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";

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

    api.github
      .connect(orgId, { installation_id: installationId })
      .then(() => {
        router.replace(`/dashboard/${orgId}/settings?github_connected=true`);
      })
      .catch((err) => {
        console.error("GitHub connect failed:", err);
        router.replace(`/dashboard/${orgId}/settings?github_error=true`);
      });
  }, [searchParams, router]);

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "var(--bg-surface)", color: "var(--text-muted)" }}>
      <p style={{ fontSize: "1rem" }}>Connecting GitHub...</p>
    </div>
  );
}

export default function GitHubCallbackPage() {
  return (
    <Suspense fallback={<div />}>
      <CallbackContent />
    </Suspense>
  );
}
