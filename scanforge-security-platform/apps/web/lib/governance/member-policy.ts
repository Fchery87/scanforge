export interface MemberPolicyInput {
  actorRole: string;
  targetRole: string;
  ownerCount: number;
}

export function canRemoveMember(input: MemberPolicyInput): boolean {
  if (input.actorRole !== "owner" && input.actorRole !== "admin") return false;
  if (input.targetRole === "owner" && input.ownerCount <= 1) return false;
  if (input.actorRole === "admin" && input.targetRole === "owner") return false;
  return true;
}

export function canChangeRole(input: { actorRole: string; targetRole: string; newRole: string; ownerCount: number }): { allowed: boolean; reason?: string } {
  if (input.actorRole !== "owner" && input.actorRole !== "admin") {
    return { allowed: false, reason: "Insufficient permissions" };
  }
  if (input.actorRole === "admin" && input.targetRole === "owner") {
    return { allowed: false, reason: "Admins cannot change owner roles" };
  }
  if (input.targetRole === "owner" && input.newRole !== "owner" && input.ownerCount <= 1) {
    return { allowed: false, reason: "Cannot remove the last owner" };
  }
  return { allowed: true };
}

export function getRoleDescription(role: string): string {
  switch (role) {
    case "owner": return "Full access including billing and deletion";
    case "admin": return "Manage projects, members, and integrations";
    case "security_reviewer": return "Review findings and manage triage";
    case "developer": return "View projects and run scans";
    case "viewer": return "Read-only access to dashboards";
    default: return "Custom role";
  }
}

export function getInviteStateDisplay(invite: { email: string; role: string; status?: string; created_at?: string }): { statusLabel: string; variant: "pending" | "accepted" | "expired" } {
  const status = invite.status ?? "pending";
  if (status === "accepted") return { statusLabel: "Accepted", variant: "accepted" };
  if (status === "expired") return { statusLabel: "Expired", variant: "expired" };
  return { statusLabel: "Pending", variant: "pending" };
}

export type IntegrationHealthState =
  | { status: "connected"; accountLogin: string; message: string }
  | { status: "disconnected"; message: string }
  | { status: "error"; message: string };

export function getIntegrationHealth(raw: unknown): IntegrationHealthState {
  if (!raw) return { status: "disconnected", message: "Not connected. Connect to enable repository syncing." };
  try {
    const data = typeof raw === "object" ? raw as Record<string, unknown> : {};
    if (data.account_login || data.accountLogin) {
      return {
        status: "connected",
        accountLogin: (data.account_login ?? data.accountLogin) as string,
        message: "Connected and syncing repositories.",
      };
    }
    return { status: "disconnected", message: "Connection incomplete. Reconnect to restore syncing." };
  } catch {
    return { status: "error", message: "Unable to determine integration status." };
  }
}

export function getDangerZoneConfirmation(orgSlug: string): string {
  return `Type "${orgSlug}" to confirm permanent deletion. This will remove all projects, repositories, findings, and audit logs.`;
}
