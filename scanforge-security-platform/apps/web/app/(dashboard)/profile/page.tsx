"use client";

import { useEffect, useState } from "react";
import { Mail, User } from "lucide-react";

import { api } from "@/lib/api";
import { authClient } from "@/lib/auth/client";
import { resolveProfileAuthState } from "@/lib/auth/profile-session";
import { PageHeader } from "@/components/scanforge/page-header";
import { PageStatePanel } from "@/components/scanforge/page-state-panel";
import { derivePageState } from "@/lib/page-surface/page-state";

export default function ProfilePage() {
  const { data: session, isPending: isSessionPending } = authClient.useSession();
  const hasSession = Boolean(session);
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const authState = resolveProfileAuthState({ isSessionPending, hasSession });
    if (authState === "pending") return;
    if (authState === "unauthenticated") {
      setUser(null);
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    setLoading(true);
    api.users.me()
      .then((data) => {
        setUser(data);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load profile"))
      .finally(() => setLoading(false));
  }, [hasSession, isSessionPending]);

  const pageState = derivePageState({
    loading,
    error,
    itemCount: user ? 1 : 0,
  });

  return (
    <div>
      <PageHeader
        title="Profile"
        description="The name and email on this account."
      />

      <PageStatePanel
        state={pageState.kind}
        message={pageState.kind === "error" ? pageState.message : undefined}
        retry={() => { setLoading(true); setError(null); }}
      >
        {pageState.kind === "ready" && (
          <div className="space-y-6">
            <div className="flex items-center gap-5 border-y border-border py-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-[14px] border border-border bg-surface-elevated text-primary">
                <User size={28} strokeWidth={1.5} />
              </div>
              <div>
                <h2 className="text-base font-semibold text-text-primary">{user?.name || "Unnamed user"}</h2>
                <p className="mt-1 flex items-center gap-1.5 text-sm text-text-tertiary">
                  <Mail className="h-3.5 w-3.5" />
                  {user?.email || "No email"}
                </p>
              </div>
            </div>

            <div className="rounded-md border border-border p-6">
              <div className="mb-3">
                <h3 className="text-sm text-text-tertiary">Preferences</h3>
              </div>
              <p className="text-sm text-text-secondary">
                Notification preferences are hidden until they are backed by persisted API data.
              </p>
            </div>
          </div>
        )}
      </PageStatePanel>
    </div>
  );
}
