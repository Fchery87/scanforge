export interface SuppressionRule {
  id: string;
  rule_type: string;
  match_criteria_json: Record<string, string>;
  reason: string;
  project_id?: string | null;
  is_active: boolean;
  created_at?: string;
  expires_at?: string | null;
  requires_approval?: boolean;
}

export function describeSuppressionScope(rule: { project_id?: string | null }): "project" | "organization" {
  return rule.project_id ? "project" : "organization";
}

export function getRuleScopeBadge(rule: { project_id?: string | null }): { label: string; variant: "default" | "secondary" } {
  return rule.project_id
    ? { label: "Project", variant: "secondary" }
    : { label: "Organization", variant: "default" };
}

export function formatExpiryDisplay(expiresAt: string | null | undefined): { label: string; isExpired: boolean; isExpiringSoon: boolean } {
  if (!expiresAt) return { label: "No expiry", isExpired: false, isExpiringSoon: false };
  const expiry = new Date(expiresAt);
  const now = new Date();
  const daysLeft = Math.ceil((expiry.getTime() - now.getTime()) / 86400000);
  if (daysLeft < 0) return { label: "Expired", isExpired: true, isExpiringSoon: false };
  if (daysLeft <= 7) return { label: `${daysLeft}d remaining`, isExpired: false, isExpiringSoon: true };
  return { label: expiry.toLocaleDateString(), isExpired: false, isExpiringSoon: false };
}

export function requiresApproval(rule: Partial<SuppressionRule>): boolean {
  if (rule.requires_approval !== undefined) return rule.requires_approval;
  if (rule.project_id) return false;
  return true;
}

export function getDeleteConfirmation(rule: SuppressionRule): string {
  const scope = describeSuppressionScope(rule);
  return `Delete this ${scope}-scoped suppression rule? Matching findings will no longer be suppressed.`;
}

export function getToggleMessage(rule: SuppressionRule): string {
  return rule.is_active
    ? `Deactivating this rule will stop suppressing matching findings.`
    : `Activating this rule will suppress matching findings going forward.`;
}

export function formatRuleSummary(rule: SuppressionRule): string {
  const scope = describeSuppressionScope(rule);
  const criteria = Object.entries(rule.match_criteria_json ?? {})
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");
  return `${scope} · ${rule.rule_type} · ${criteria || "no criteria"}`;
}
