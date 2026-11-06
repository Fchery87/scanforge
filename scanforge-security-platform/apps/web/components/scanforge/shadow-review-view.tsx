"use client";

import { useState } from "react";

import { CapabilityCoverage } from "@/components/scanforge/capability-coverage";
import type { ShadowReview, ShadowReviewResult } from "@/lib/api-schemas";
import { cn } from "@/lib/utils";

export const SHADOW_LABELS = [
  { value: "useful", text: "Useful" },
  { value: "not_useful", text: "Not useful" },
  { value: "incorrect", text: "Incorrect" },
  { value: "duplicate", text: "Duplicate" },
  { value: "missing_context", text: "Missing context" },
] as const;

const CLASSIFICATION_LABELS: Record<string, string> = {
  new: "New",
  existing: "Existing",
  unknown: "Unknown",
};

// Unknown is deliberately loud and never styled as clean: it means ScanForge could not tell.
const CLASSIFICATION_STYLES: Record<string, string> = {
  new: "border-danger/30 bg-danger/10 text-danger",
  existing: "border-border text-text-secondary",
  unknown: "border-warning/30 bg-warning/10 text-warning-foreground",
};

function humanize(value: string) {
  return value.replace(/_/g, " ");
}

function formatDuration(duration: ShadowReview["duration"]) {
  if (duration.state === "unavailable" || duration.total_ms == null) return "Not measured";
  const seconds = (duration.total_ms / 1000).toFixed(1);
  return duration.state === "partial" ? `${seconds}s (some scanners did not report)` : `${seconds}s`;
}

function formatCost(cost: ShadowReview["cost_estimate"]) {
  return cost.state === "estimated" ? "Estimated" : `Not measured${cost.reason ? ` (${cost.reason})` : ""}`;
}

function shortSha(sha?: string | null) {
  return sha ? sha.slice(0, 12) : "unresolved";
}

function Revision({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs text-text-tertiary">{label}</dt>
      <dd className={cn("font-mono text-sm", value ? "text-text-primary" : "text-text-tertiary")}>{shortSha(value)}</dd>
    </div>
  );
}

function ResultRow({
  result,
  onLabel,
}: {
  result: ShadowReviewResult;
  onLabel: (candidateId: string, label: string) => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const labels = result.labels ?? [];

  async function choose(label: string) {
    if (!result.candidate_id) return;
    setPending(true);
    setError("");
    try {
      await onLabel(result.candidate_id, label);
    } catch (err: any) {
      setError(err?.message || "Could not save label");
    } finally {
      setPending(false);
    }
  }

  return (
    <li className="rounded-md border border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded border px-2 py-0.5 text-xs font-medium",
            CLASSIFICATION_STYLES[result.classification] ?? CLASSIFICATION_STYLES.unknown,
          )}
        >
          {CLASSIFICATION_LABELS[result.classification] ?? result.classification}
        </span>
        <span className="font-mono text-xs text-text-secondary">{result.scanner ?? "unknown scanner"}</span>
        {result.candidate_state ? (
          <span className="text-xs text-text-tertiary">candidate {result.candidate_state}</span>
        ) : null}
      </div>
      <p className="mt-2 break-all font-mono text-xs text-text-primary">
        {result.path ? `${result.path}${result.line_start != null ? `:${result.line_start}` : ""}` : result.fingerprint}
      </p>
      <p className="mt-1 text-xs text-text-secondary">{humanize(result.reason)}</p>

      {result.candidate_id ? (
        <div className="mt-3" role="group" aria-label="Reviewer label">
          <div className="flex flex-wrap gap-2">
            {SHADOW_LABELS.map((option) => (
              <button
                key={option.value}
                type="button"
                disabled={pending}
                onClick={() => choose(option.value)}
                className="rounded border border-border px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"
              >
                {option.text}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-text-tertiary">
            Labels are evaluation data only. They do not suppress or change any finding.
          </p>
          {labels.length ? (
            <ul className="mt-1 text-xs text-text-secondary">
              {labels.map((item) => (
                <li key={`${item.actor_user_id}-${item.label}`}>
                  {humanize(item.label)} · {item.actor_user_id ?? "removed user"} ·{" "}
                  {new Date(item.labeled_at).toLocaleString()}
                </li>
              ))}
            </ul>
          ) : null}
          {error ? <p className="mt-1 text-xs text-danger">{error}</p> : null}
        </div>
      ) : null}
    </li>
  );
}

const STATE_NOTICES: Record<string, string> = {
  pending: "This shadow run has not finished. Results will appear when it completes.",
  failed: "This shadow run did not complete, so there are no results to review. This is not a clean result.",
  empty:
    "The analyzers reported no results within their declared scope. This does not mean the change is safe; see coverage above.",
};

export function ShadowReviewView({
  review,
  onLabel,
}: {
  review: ShadowReview;
  onLabel: (candidateId: string, label: string) => Promise<void>;
}) {
  const results = review.results ?? [];
  const limitations = review.limitations ?? [];
  const counts = review.classification_counts;

  return (
    <div>
      <section className="mb-6" aria-label="Analyzed revisions">
        <h2 className="mb-3 text-sm font-medium text-text-primary">
          Analyzed revisions{review.revisions.pull_request_number != null ? ` · PR #${review.revisions.pull_request_number}` : ""}
        </h2>
        <dl className="grid gap-4 sm:grid-cols-3">
          <Revision label="Base" value={review.revisions.base_sha} />
          <Revision label="Head" value={review.revisions.head_sha} />
          <Revision label="Merge base" value={review.revisions.merge_base_sha} />
        </dl>
        {review.revisions.head_is_fork ? (
          <p className="mt-2 text-xs text-text-secondary">Head is from a fork.</p>
        ) : null}
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-text-tertiary">Duration</dt>
            <dd className="text-sm text-text-primary">{formatDuration(review.duration)}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-tertiary">Cost estimate</dt>
            <dd className="text-sm text-text-primary">{formatCost(review.cost_estimate)}</dd>
          </div>
        </dl>
      </section>

      <CapabilityCoverage coverage={review.capability_coverage ?? []} />

      {STATE_NOTICES[review.state] ? (
        <p role="status" className="mb-6 rounded-md border border-border p-4 text-sm text-text-secondary">
          {STATE_NOTICES[review.state]}
        </p>
      ) : null}

      {limitations.length ? (
        <section
          className="mb-6 rounded-md border border-warning/30 bg-warning/10 p-4"
          aria-label="Limitations"
        >
          <h2 className="mb-2 text-sm font-medium text-warning-foreground">Limitations: partial result</h2>
          <ul className="list-disc space-y-1 pl-5 text-xs text-warning-foreground">
            {limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {review.classification_state === "classified" ? (
        <section aria-label="Classified results">
          <h2 className="mb-1 text-sm font-medium text-text-primary">Results</h2>
          <p className="mb-3 text-xs text-text-secondary">
            {counts.new} new · {counts.existing} existing · {counts.unknown} unknown
          </p>
          {results.length ? (
            <ul className="space-y-3">
              {results.map((result) => (
                <ResultRow key={result.fingerprint} result={result} onLabel={onLabel} />
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
