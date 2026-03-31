"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Mail, User } from "lucide-react";
import { api } from "@/lib/api";
import { authClient } from "@/lib/auth/client";
import { resolveProfileAuthState } from "@/lib/auth/profile-session";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonList } from "@/components/scanforge/loading-skeleton";

export default function ProfilePage() {
  const { data: session, isPending: isSessionPending } = authClient.useSession();
  const hasSession = Boolean(session);
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log("[Profile] Session state:", { 
      hasSession, 
      isSessionPending, 
      sessionData: session ? "present" : "null",
      sessionUser: session?.user?.email 
    });

    const authState = resolveProfileAuthState({
      isSessionPending,
      hasSession,
    });

    console.log("[Profile] Auth state:", authState);

    if (authState === "pending") {
      return;
    }

    if (authState === "unauthenticated") {
      setUser(null);
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    setLoading(true);
    api.users.me()
      .then((data) => {
        console.log("[Profile] User data loaded:", data);
        setUser(data);
        setError(null);
      })
      .catch((err) => {
        console.error("[Profile] Error loading user:", err);
        setError(err instanceof Error ? err.message : "Failed to load profile");
      })
      .finally(() => setLoading(false));
  }, [hasSession, isSessionPending, session]);

  return (
    <div>
      <PageHeader
        title="Profile"
        description="View your authenticated account details"
      />

      {loading ? (
        <SkeletonList rows={3} />
      ) : error ? (
        <div className="rounded-xl border border-danger/30 bg-danger/5 p-6 text-sm text-danger">
          {error}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center gap-5 rounded-xl border border-border bg-surface p-6 animate-fade-up">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/20 text-primary">
              <User size={28} strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-lg font-semibold font-display">{user?.name || "Unnamed user"}</h2>
              <p className="flex items-center gap-1.5 text-sm text-text-tertiary mt-0.5">
                <Mail className="h-3.5 w-3.5" /> {user?.email || "No email returned by identity provider"}
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-surface p-6 animate-fade-up stagger-1">
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="h-4 w-4 text-text-secondary" />
              <h3 className="text-sm font-semibold font-display">Preferences</h3>
            </div>
            <p className="text-sm text-text-secondary">
              Notification preferences are hidden until they are backed by persisted API data.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
