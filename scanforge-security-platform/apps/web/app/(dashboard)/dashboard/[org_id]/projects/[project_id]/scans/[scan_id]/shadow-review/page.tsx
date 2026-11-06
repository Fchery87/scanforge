"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { api } from "@/lib/api";
import type { ShadowReview } from "@/lib/api-schemas";
import { PageHeader } from "@/components/scanforge/page-header";
import { PageStatePanel } from "@/components/scanforge/page-state-panel";
import { ShadowReviewView } from "@/components/scanforge/shadow-review-view";

// Internal evaluation view. Nothing on this page is published to GitHub.
export default function ShadowReviewPage() {
  const { org_id, project_id, scan_id } = useParams<{ org_id: string; project_id: string; scan_id: string }>();
  const [review, setReview] = useState<ShadowReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReview(await api.scans.shadowReview(org_id, project_id, scan_id));
      setError("");
    } catch (err: any) {
      setError(err?.message || "Failed to load shadow review");
    } finally {
      setLoading(false);
    }
  }, [org_id, project_id, scan_id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleLabel(candidateId: string, label: string) {
    await api.scans.labelShadowCandidate(org_id, project_id, scan_id, candidateId, label);
    setReview(await api.scans.shadowReview(org_id, project_id, scan_id));
  }

  return (
    <div>
      <Link
        href={`/dashboard/${org_id}/projects/${project_id}/scans/${scan_id}`}
        className="mb-4 inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to scan
      </Link>
      <PageHeader
        title="Shadow review"
        description="Internal evaluation of a pull request analysis. Nothing here is published to GitHub."
      />
      {loading && !review ? (
        <PageStatePanel state="loading" />
      ) : error && !review ? (
        <PageStatePanel state="error" message={error} retry={load} />
      ) : review ? (
        <ShadowReviewView review={review} onLabel={handleLabel} />
      ) : null}
    </div>
  );
}
