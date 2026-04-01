export function formatRelativeTime(dateStr: string, now = Date.now()) {
  const value = new Date(dateStr).getTime();
  if (Number.isNaN(value)) return "unknown";

  const seconds = Math.floor((now - value) / 1000);
  if (seconds < 60) return "just now";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;

  const days = Math.floor(hours / 24);
  return `${days} days ago`;
}

export function formatScanDuration(summary: {
  duration_ms?: number | null;
  duration_seconds?: number | null;
}) {
  if (summary.duration_ms != null) {
    if (summary.duration_ms < 1000) return `${summary.duration_ms}ms`;
    return `${(summary.duration_ms / 1000).toFixed(1)}s`;
  }

  if (summary.duration_seconds != null) {
    return `${Number(summary.duration_seconds).toFixed(1)}s`;
  }

  return "—";
}

export function summarizeExportSize(sizeBytes: number | null | undefined) {
  if (!sizeBytes || sizeBytes <= 0) return null;
  return `${(sizeBytes / 1024).toFixed(1)} KB`;
}
