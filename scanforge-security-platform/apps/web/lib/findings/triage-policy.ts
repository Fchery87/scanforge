export interface FindingStatus {
  status: string;
  due_date?: string | null;
}

export function canBulkAction(action: string, selectedStatuses: string[]): { allowed: boolean; reason?: string } {
  if (selectedStatuses.length === 0) {
    return { allowed: false, reason: "No findings selected" };
  }
  if (action === "resolve" && selectedStatuses.every((s) => s === "fixed")) {
    return { allowed: false, reason: "All selected findings are already fixed" };
  }
  return { allowed: true };
}

export function isOverdue(dueDate: string | null | undefined): boolean {
  if (!dueDate) return false;
  return new Date(dueDate) < new Date();
}

export function getSLABadge(dueDate: string | null | undefined): { label: string; variant: "danger" | "warning" | "success" | "none" } {
  if (!dueDate) return { label: "No SLA", variant: "none" };
  const now = new Date();
  const due = new Date(dueDate);
  const daysLeft = Math.ceil((due.getTime() - now.getTime()) / 86400000);
  if (daysLeft < 0) return { label: "Overdue", variant: "danger" };
  if (daysLeft <= 3) return { label: `${daysLeft}d left`, variant: "warning" };
  return { label: `${daysLeft}d left`, variant: "success" };
}

export function triageActionLabel(status: string): string {
  switch (status) {
    case "open": return "Triage";
    case "fixed": return "Verify Fix";
    case "suppressed": return "Review Suppression";
    case "accepted_risk": return "Risk Accepted";
    case "duplicate": return "Duplicate";
    default: return status;
  }
}
