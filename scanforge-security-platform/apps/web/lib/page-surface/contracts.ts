export type GithubIntegrationState =
  | { status: "connected"; accountLogin: string; accountType?: string }
  | { status: "disconnected" }
  | { status: "error"; message: string };

export function normalizeGithubIntegrationState(raw: unknown): GithubIntegrationState {
  if (!raw) return { status: "disconnected" };
  try {
    const data = typeof raw === "object" ? raw as Record<string, unknown> : {};
    if (data.account_login || data.accountLogin) {
      return {
        status: "connected",
        accountLogin: (data.account_login ?? data.accountLogin) as string,
        accountType: (data.account_type ?? data.accountType) as string | undefined,
      };
    }
    return { status: "disconnected" };
  } catch {
    return { status: "error", message: "Failed to parse integration data" };
  }
}

export type MemberState = {
  userId: string;
  userName?: string;
  userEmail?: string;
  role: string;
  isOwner: boolean;
};

export function normalizeMember(raw: Record<string, unknown>): MemberState {
  return {
    userId: (raw.user_id ?? raw.id) as string,
    userName: raw.user_name as string | undefined,
    userEmail: raw.user_email as string | undefined,
    role: (raw.role ?? "viewer") as string,
    isOwner: raw.role === "owner",
  };
}

export type OnboardingNextAction = {
  id: string;
  label: string;
  isPrimary: boolean;
  url?: string;
};

export function deriveOnboardingNextActions(
  steps: Array<{ id: string; completed: boolean; action_url?: string | null; label?: string }>
): OnboardingNextAction[] {
  const incomplete = steps.filter((s) => !s.completed);
  const first = incomplete[0];
  if (!first) return [];
  return [
    {
      id: first.id,
      label: first.label ?? first.id,
      isPrimary: true,
      url: first.action_url ?? undefined,
    },
  ];
}

export type ScanLifecycleSummary = {
  phase: "active" | "completed" | "failed" | "stale";
  canRerun: boolean;
  canDelete: boolean;
  statusLabel: string;
};

export function deriveScanLifecycle(scan: { status: string; scanner_runs?: unknown[] }): ScanLifecycleSummary {
  const status = scan.status?.toLowerCase() ?? "";
  const phase = status === "running" || status === "queued" ? "active"
    : status === "failed" || status === "canceled" ? "failed"
    : status === "completed" ? "completed"
    : "stale";
  return {
    phase,
    canRerun: ["failed", "canceled", "completed"].includes(status),
    canDelete: ["queued", "failed", "canceled"].includes(status),
    statusLabel: status || "unknown",
  };
}

export type SuppressionSummary = {
  scope: "organization" | "project";
  isActive: boolean;
  hasExpiry: boolean;
};

export function deriveSuppressionSummary(rule: Record<string, unknown>): SuppressionSummary {
  const hasProjectId = !!rule.project_id;
  return {
    scope: hasProjectId ? "project" : "organization",
    isActive: rule.is_active !== false,
    hasExpiry: !!rule.expires_at,
  };
}
