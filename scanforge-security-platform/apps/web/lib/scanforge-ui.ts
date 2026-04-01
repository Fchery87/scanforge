const SEVERITY_LABELS = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
} as const;

const STATUS_LABELS = {
  open: "Open",
  fixed: "Fixed",
  suppressed: "Suppressed",
  accepted_risk: "Accepted",
  duplicate: "Duplicate",
  completed: "Completed",
  failed: "Failed",
  running: "Running",
  queued: "Queued",
  canceled: "Canceled",
} as const;

export function deriveRiskGrade(stats: {
  critical_findings?: number;
  open_findings?: number;
  by_severity?: { critical?: number };
  open?: number;
} | null | undefined) {
  if (!stats) return null;

  const criticalCount = stats.critical_findings ?? stats.by_severity?.critical ?? 0;
  const openCount = stats.open_findings ?? stats.open ?? 0;
  const penalty = criticalCount * 25 + openCount * 3;
  const score = Math.max(0, 100 - penalty);

  if (score >= 95) return "A+";
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

export function getSeverityMeta(severity: string) {
  const key = severity.toLowerCase() as keyof typeof SEVERITY_LABELS;
  if (key in SEVERITY_LABELS) {
    return {
      key,
      label: SEVERITY_LABELS[key],
      tone: key,
    } as const;
  }

  return {
    key,
    label: toTitleCase(severity),
    tone: "neutral" as const,
  };
}

export function getStatusMeta(status: string) {
  const key = status.toLowerCase() as keyof typeof STATUS_LABELS;
  if (key in STATUS_LABELS) {
    return {
      key,
      label: STATUS_LABELS[key],
      tone: getStatusTone(key),
    } as const;
  }

  return {
    key,
    label: toTitleCase(status),
    tone: "neutral" as const,
  };
}

function getStatusTone(status: keyof typeof STATUS_LABELS) {
  if (status === "fixed" || status === "completed") return "success" as const;
  if (status === "failed") return "danger" as const;
  if (status === "running") return "primary" as const;
  if (status === "accepted_risk") return "info" as const;
  if (status === "open" || status === "canceled") return "warning" as const;
  return "neutral" as const;
}

function toTitleCase(value: string) {
  if (!value) return "Unknown";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
