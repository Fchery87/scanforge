"use client";

import { cn } from "@/lib/utils";

interface ScannerCoverage {
  scanner_name: string;
  state: string;
  reasons?: string[];
  declared_scope?: string | null;
  inputs_found?: number | null;
  inputs_supported?: number | null;
  unsupported_inputs?: string[] | null;
  exclusions?: string[] | null;
  parse_failures?: number | null;
  truncated?: boolean | null;
  timed_out?: boolean | null;
}

interface CapabilityCoverageItem {
  capability: string;
  state: string;
  reasons?: string[];
  scanners?: ScannerCoverage[];
}

const CAPABILITY_LABELS: Record<string, string> = {
  secrets: "Secrets",
  sast: "Source code (SAST)",
  dependencies: "Dependencies",
  iac: "Infrastructure as code",
};

const STATE_LABELS: Record<string, string> = {
  complete: "Complete for declared scope",
  partial: "Partial",
  unknown: "Unknown",
  not_applicable: "Not applicable",
};

// Partial and unknown are deliberately loud: neither may read as a clean result.
const STATE_STYLES: Record<string, string> = {
  complete: "border-border text-text-primary",
  not_applicable: "border-border text-text-secondary",
  partial: "border-warning/30 bg-warning/10 text-warning-foreground",
  unknown: "border-warning/30 bg-warning/10 text-warning-foreground",
};

function humanize(reason: string) {
  return reason.replace(/_/g, " ");
}

// Only analyzer-reported measurements are listed; absent values are omitted, never estimated.
function measurements(scanner: ScannerCoverage): string[] {
  const lines: string[] = [];
  if (scanner.declared_scope) lines.push(`Scope: ${scanner.declared_scope}`);
  if (scanner.inputs_found != null) lines.push(`Inputs found: ${scanner.inputs_found}`);
  if (scanner.inputs_supported != null) lines.push(`Inputs supported: ${scanner.inputs_supported}`);
  if (scanner.unsupported_inputs?.length) lines.push(`Unsupported: ${scanner.unsupported_inputs.join(", ")}`);
  if (scanner.exclusions?.length) lines.push(`Exclusions: ${scanner.exclusions.join(", ")}`);
  if (scanner.parse_failures != null) lines.push(`Parse failures: ${scanner.parse_failures}`);
  if (scanner.truncated) lines.push("Output truncated");
  if (scanner.timed_out) lines.push("Timed out");
  return lines;
}

export function CapabilityCoverage({ coverage, className }: { coverage: CapabilityCoverageItem[]; className?: string }) {
  if (!coverage.length) return null;

  return (
    <section className={cn("mb-8", className)} aria-label="Coverage by capability">
      <h2 className="mb-3 text-sm font-medium text-text-primary">Coverage</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {coverage.map((item) => (
          <div
            key={item.capability}
            className={cn("rounded-md border p-4", STATE_STYLES[item.state] ?? STATE_STYLES.unknown)}
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm font-medium">{CAPABILITY_LABELS[item.capability] ?? item.capability}</span>
              <span className="text-xs">{STATE_LABELS[item.state] ?? item.state}</span>
            </div>
            {item.reasons?.length ? (
              <p className="mt-1 text-xs text-text-secondary">{item.reasons.map(humanize).join("; ")}</p>
            ) : null}
            <ul className="mt-3 space-y-2">
              {(item.scanners ?? []).map((scanner) => (
                <li key={scanner.scanner_name} className="text-xs">
                  <span className="font-mono">{scanner.scanner_name}</span>
                  <span className="text-text-tertiary"> · {STATE_LABELS[scanner.state] ?? scanner.state}</span>
                  {measurements(scanner).map((line) => (
                    <div key={line} className="text-text-secondary">{line}</div>
                  ))}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
