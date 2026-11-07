type Signature = Record<string, unknown> | null | undefined;

interface ExplainableEvent {
  event_type: string;
  metadata_json?: Record<string, unknown> | null;
}

const SIGNATURE_FIELDS: Array<[string, string]> = [
  ["scanner_version", "scanner version"],
  ["parser_version", "parser version"],
  ["rules_digest", "rules digest"],
  ["fingerprint_version", "fingerprint version"],
];

function analyzerChanges(baseline: Signature, current: Signature): string[] {
  if (!baseline || !current) return [];
  return SIGNATURE_FIELDS.flatMap(([key, label]) =>
    baseline[key] !== current[key] ? [`${label} ${baseline[key] ?? "unknown"} to ${current[key] ?? "unknown"}`] : []
  );
}

/** One-sentence reviewer-facing explanation for lifecycle events that need one. */
export function explainFindingEvent(event: ExplainableEvent): string | null {
  const meta = event.metadata_json ?? {};
  switch (event.event_type) {
    case "absence_not_credited": {
      const blocked = Array.isArray(meta.blocked_by) ? meta.blocked_by : [];
      if (blocked.includes("analyzer_baseline_unknown")) {
        return "Absence not credited: this finding has no recorded analyzer to compare against, so it cannot close automatically.";
      }
      const changes = analyzerChanges(meta.baseline as Signature, meta.current as Signature);
      return changes.length
        ? `Absence not credited: the analyzer changed (${changes.join("; ")}), so the missing result is not evidence of a fix.`
        : "Absence not credited: the analyzer is not comparable with the one that last reported this finding.";
    }
    case "successor_linked":
      return "A successor (fp.v3) finding exactly matches this legacy finding. Review decisions were not transferred; resolve this one deliberately.";
    case "predecessor_linked":
      return "This finding exactly matches a legacy (fp.v2) finding. Review decisions were not transferred.";
    default:
      return null;
  }
}
