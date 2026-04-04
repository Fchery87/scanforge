export type ScanPhase = "active" | "completed" | "failed" | "stale";

const STALE_ACTIVE_SCAN_MS = 60 * 60 * 1000;

export interface ScanInput {
  status: string;
  scanner_runs?: unknown[];
  created_at?: string;
}

export function isStaleActiveScan(scan: ScanInput, now: Date = new Date()): boolean {
  const status = scan.status?.toLowerCase() ?? "";
  if (status !== "running" && status !== "queued") return false;
  if (!scan.created_at) return false;

  const createdAtMs = new Date(scan.created_at).getTime();
  if (Number.isNaN(createdAtMs)) return false;

  return now.getTime() - createdAtMs >= STALE_ACTIVE_SCAN_MS;
}

export function deriveScanPhase(scan: ScanInput, now: Date = new Date()): ScanPhase {
  const status = scan.status?.toLowerCase() ?? "";
  if (status === "running" || status === "queued") {
    return isStaleActiveScan(scan, now) ? "stale" : "active";
  }
  if (status === "failed" || status === "canceled") return "failed";
  if (status === "completed") return "completed";
  return "stale";
}

export function canRerunScan(status: string): boolean {
  return ["failed", "canceled", "completed"].includes(status?.toLowerCase());
}

export function canDeleteScan(status: string): boolean {
  return ["queued", "failed", "canceled"].includes(status?.toLowerCase());
}

export function canCancelScan(status: string): boolean {
  return ["queued", "running"].includes(status?.toLowerCase());
}

export function deriveRerunPayload(scan: { repository_id: string; branch_name?: string }): {
  repository_id: string;
  trigger_type: string;
  branch_name?: string;
} {
  return {
    repository_id: scan.repository_id,
    trigger_type: "manual",
    branch_name: scan.branch_name || undefined,
  };
}

export function formatScanSummary(scan: {
  status: string;
  branch_name?: string;
  created_at?: string;
  summary_json?: Record<string, unknown>;
}): {
  statusLabel: string;
  branch: string;
  findingCount: number;
  createdAt: string;
} {
  const summary = scan.summary_json ?? {};
  return {
    statusLabel: scan.status ?? "unknown",
    branch: scan.branch_name ?? "default",
    findingCount: (summary.finding_count as number) ?? 0,
    createdAt: scan.created_at ?? "",
  };
}

export function getArtifactAvailability(run: { artifact_uri?: string | null; status?: string }): {
  available: boolean;
  uri?: string;
  reason?: string;
} {
  if (run.artifact_uri) return { available: true, uri: run.artifact_uri };
  if (run.status === "failed") return { available: false, reason: "Run failed — no artifact generated" };
  if (run.status === "running" || run.status === "queued") return { available: false, reason: "Run in progress — artifact pending" };
  return { available: false, reason: "No artifact available" };
}

export function getScannerRunStatus(run: { status?: string }, scan?: ScanInput, now: Date = new Date()): {
  label: string;
  variant: "active" | "success" | "error" | "pending";
} {
  const status = run.status?.toLowerCase() ?? "";
  if (status === "running" || status === "queued") {
    if (scan && isStaleActiveScan(scan, now)) return { label: "stale", variant: "error" };
    return { label: status, variant: "active" };
  }
  if (status === "completed" || status === "success") return { label: "completed", variant: "success" };
  if (status === "failed" || status === "error") return { label: "failed", variant: "error" };
  return { label: status || "unknown", variant: "pending" };
}
