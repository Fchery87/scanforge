"use client";

import { Suspense, useEffect, useState, useCallback, useRef } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Search, Download, ChevronLeft, ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { FindingsTable } from "@/components/scanforge/findings-table";
import { FindingsSavedViewBar } from "@/components/scanforge/findings-saved-view-bar";
import { FilterBar } from "@/components/scanforge/filter-bar";
import FindingDrawer from "./FindingDrawer";
import {
  parseFindingsFilters,
  serializeFindingsFilters,
  hasActiveFilters,
  formatExportScope,
} from "@/lib/findings/filter-state";
import { canBulkAction } from "@/lib/findings/triage-policy";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const CATEGORIES = [
  "vulnerability",
  "secret",
  "dependency_outdated",
  "malicious_pattern",
  "code_quality",
];
const STATUSES = ["open", "fixed", "suppressed", "accepted_risk", "duplicate"];

// ─── Pagination ───────────────────────────────────────────────────────────────

interface PaginationProps {
  page: number;
  total: number;
  limit: number;
  onPageChange: (p: number) => void;
}

function Pagination({ page, total, limit, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const start = total === 0 ? 0 : page * limit + 1;
  const end = Math.min((page + 1) * limit, total);

  // Build page number window: always show first, last, current ±1, plus ellipsis
  const buildPages = (): (number | "ellipsis-start" | "ellipsis-end")[] => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i);
    }
    const pages: (number | "ellipsis-start" | "ellipsis-end")[] = [];
    const left = Math.max(1, page - 1);
    const right = Math.min(totalPages - 2, page + 1);

    pages.push(0);
    if (left > 1) pages.push("ellipsis-start");
    for (let i = left; i <= right; i++) pages.push(i);
    if (right < totalPages - 2) pages.push("ellipsis-end");
    pages.push(totalPages - 1);
    return pages;
  };

  const pages = buildPages();

  return (
    <div className="flex items-center justify-between px-1 py-4 mt-2">
      <p className="text-xs text-text-tertiary font-mono">
        Showing{" "}
        <span className="text-text-secondary font-medium">
          {start}–{end}
        </span>{" "}
        of{" "}
        <span className="text-text-secondary font-medium">{total}</span>{" "}
        Findings
      </p>

      <div className="flex items-center gap-1">
        <button
          disabled={page === 0}
          onClick={() => onPageChange(page - 1)}
          aria-label="Previous page"
          className={cn(
            "h-8 w-8 rounded-lg text-xs font-medium flex items-center justify-center transition-colors",
            page === 0
              ? "text-text-tertiary opacity-40 cursor-not-allowed"
              : "text-text-secondary hover:bg-surface-hover"
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        {pages.map((p, i) =>
          p === "ellipsis-start" || p === "ellipsis-end" ? (
            <span
              key={`${p}-${i}`}
              className="h-8 w-8 flex items-center justify-center text-xs text-text-tertiary select-none"
            >
              &hellip;
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p as number)}
              aria-label={`Page ${(p as number) + 1}`}
              aria-current={p === page ? "page" : undefined}
              className={cn(
                "h-8 w-8 rounded-lg text-xs font-medium flex items-center justify-center transition-colors",
                p === page
                  ? "bg-primary text-white shadow-sm"
                  : "text-text-secondary hover:bg-surface-hover"
              )}
            >
              {(p as number) + 1}
            </button>
          )
        )}

        <button
          disabled={(page + 1) * limit >= total}
          onClick={() => onPageChange(page + 1)}
          aria-label="Next page"
          className={cn(
            "h-8 w-8 rounded-lg text-xs font-medium flex items-center justify-center transition-colors",
            (page + 1) * limit >= total
              ? "text-text-tertiary opacity-40 cursor-not-allowed"
              : "text-text-secondary hover:bg-surface-hover"
          )}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ─── Main Content ─────────────────────────────────────────────────────────────

function FindingsContent() {
  const { org_id, project_id } = useParams();
  const searchParamsObj = useSearchParams();
  const router = useRouter();

  const [findings, setFindings] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<string | null>(null);
  const initialFilters = parseFindingsFilters(searchParamsObj);
  const [severity, setSeverity] = useState(initialFilters.severity ?? "");
  const [category, setCategory] = useState(initialFilters.category ?? "");
  const [status, setStatus] = useState(initialFilters.status ?? "");
  const [search, setSearch] = useState(initialFilters.search ?? "");
  const [page, setPage] = useState(0);
  const [repositoryId, setRepositoryId] = useState(initialFilters.repositoryId ?? "");
  const [scanner, setScanner] = useState(initialFilters.scanner ?? "");
  const [repos, setRepos] = useState<any[]>([]);
  const [sortBy, setSortBy] = useState<string>("first_seen_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [savedViews, setSavedViews] = useState<Array<{ name: string; filters: Record<string, string> }>>([]);
  const limit = 30;

  // ── URL sync ────────────────────────────────────────────────────────────────
  const _updateUrl = useCallback(
    (overrides?: Record<string, string>) => {
      const filters = { severity, category, status, repositoryId, scanner, search };
      const serialized = serializeFindingsFilters({ ...filters, ...overrides });
      const params = new URLSearchParams(serialized);
      const qs = params.toString();
      router.push(`?${qs}`, { scroll: false });
    },
    [severity, category, status, repositoryId, scanner, search, router]
  );

  // ── Data fetching ───────────────────────────────────────────────────────────
  const fetchFindings = useCallback(async () => {
    setLoading(true);
    const params: Record<string, string> = {
      skip: String(page * limit),
      limit: String(limit),
      ...serializeFindingsFilters({ severity, category, status, repositoryId, scanner, search }),
    };
    if (params.repositoryId) {
      params.repository_id = params.repositoryId;
      delete params.repositoryId;
    }
    try {
      const res = await api.findings.list(
        org_id as string,
        project_id as string,
        params
      );
      setFindings(res.items ?? []);
      setTotal(res.total ?? 0);
    } catch {
      setFindings([]);
    } finally {
      setLoading(false);
    }
  }, [
    org_id,
    project_id,
    page,
    severity,
    category,
    status,
    search,
    repositoryId,
    scanner,
  ]);

  const fetchRepos = useCallback(async () => {
    try {
      const res = await api.repositories.list(
        org_id as string,
        project_id as string
      );
      setRepos(res.items ?? []);
    } catch {
      // ignore fetch error
    }
  }, [org_id, project_id]);

  useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos]);

  useEffect(() => {
    const filters = parseFindingsFilters(searchParamsObj);
    if (filters.severity !== severity) setSeverity(filters.severity ?? "");
    if (filters.category !== category) setCategory(filters.category ?? "");
    if (filters.repositoryId !== repositoryId) setRepositoryId(filters.repositoryId ?? "");
    if (filters.scanner !== scanner) setScanner(filters.scanner ?? "");
    if (filters.status !== status) setStatus(filters.status ?? "");
    if (filters.search !== search) setSearch(filters.search ?? "");
  }, [searchParamsObj]);

  // ── Selection ───────────────────────────────────────────────────────────────
  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleAll = () => {
    setSelected((prev) =>
      prev.length === sortedFindings.length
        ? []
        : sortedFindings.map((f: any) => f.id)
    );
  };

  // ── Keyboard navigation ─────────────────────────────────────────────────────
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (
        !e.target ||
        (e.target as HTMLElement).tagName === "INPUT" ||
        (e.target as HTMLElement).tagName === "TEXTAREA" ||
        (e.target as HTMLElement).tagName === "SELECT"
      )
        return;
      const sf = sortedFindingsRef.current;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedIndex((i) => Math.min(i + 1, sf.length - 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" && focusedIndex >= 0) {
        e.preventDefault();
        setSelectedFinding(sf[focusedIndex].id);
      } else if (e.key === "Escape") {
        setSelectedFinding(null);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [focusedIndex]);

  useEffect(() => {
    setFocusedIndex(-1);
  }, [findings]);

  // ── Sort ────────────────────────────────────────────────────────────────────
  const toggleSort = (col: string) => {
    if (sortBy === col) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  const severityOrder: Record<string, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
    info: 4,
  };

  const sortedFindings = [...findings].sort((a: any, b: any) => {
    let cmp = 0;
    if (sortBy === "severity") {
      cmp =
        (severityOrder[a.severity] ?? 5) - (severityOrder[b.severity] ?? 5);
    } else if (sortBy === "first_seen_at") {
      cmp =
        new Date(a.first_seen_at).getTime() -
        new Date(b.first_seen_at).getTime();
    } else if (sortBy === "category") {
      cmp = a.category.localeCompare(b.category);
    } else if (sortBy === "status") {
      cmp = a.status.localeCompare(b.status);
    } else if (sortBy === "due_date") {
      cmp =
        new Date(a.due_date || "9999-12-31").getTime() -
        new Date(b.due_date || "9999-12-31").getTime();
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  const sortedFindingsRef = useRef(sortedFindings);
  sortedFindingsRef.current = sortedFindings;

  // ── Bulk actions ────────────────────────────────────────────────────────────
  const handleBulkResolve = async () => {
    const selectedStatuses = findings
      .filter((f) => selected.includes(f.id))
      .map((f) => f.status);
    const check = canBulkAction("resolve", selectedStatuses);
    if (!check.allowed) {
      alert(check.reason);
      return;
    }
    try {
      await api.findings.bulk(org_id as string, project_id as string, {
        finding_ids: selected,
        action: "resolve",
        reason: "Bulk resolved from findings page",
      });
      setSelected([]);
      fetchFindings();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSuppress = (reason: string) => {
    if (selected.length === 0) return;
    api.findings
      .bulk(org_id as string, project_id as string, {
        finding_ids: selected,
        action: "suppress",
        reason,
      })
      .then(() => {
        setSelected([]);
        fetchFindings();
      })
      .catch(console.error);
  };

  const handleBulkTriage = (action: "accept_risk" | "mark_duplicate", reason: string) => {
    if (selected.length === 0) return;
    api.findings
      .bulk(org_id as string, project_id as string, {
        finding_ids: selected,
        action,
        reason,
      })
      .then(() => {
        setSelected([]);
        fetchFindings();
      })
      .catch(console.error);
  };

  const handleExportFiltered = async (format: "csv" | "json") => {
    const filters = { severity, category, status, repositoryId, scanner, search };
    const scope = formatExportScope(filters, total);
    if (!confirm(`Export: ${scope} as ${format.toUpperCase()}?`)) return;
    try {
      await api.exports.create(org_id as string, project_id as string, {
        export_type: "findings",
        format,
        title: `Filtered findings - ${new Date().toISOString().slice(0, 10)}`,
        filters: serializeFindingsFilters(filters),
      });
      alert(`Export started. Check the Exports page for download.`);
    } catch (err) {
      console.error(err);
    }
  };

  const filters = { severity, category, status, repositoryId, scanner, search };
  const isActive = hasActiveFilters(filters);

  const clearAllFilters = () => {
    setSeverity("");
    setCategory("");
    setStatus("");
    setSearch("");
    setRepositoryId("");
    setScanner("");
    setPage(0);
  };

  const handleSaveView = (payload: { name: string; filters: Record<string, string> }) => {
    setSavedViews((prev) => [...prev, payload]);
  };

  const handleApplyView = (viewFilters: Record<string, string>) => {
    setSeverity(viewFilters.severity ?? "");
    setCategory(viewFilters.category ?? "");
    setStatus(viewFilters.status ?? "");
    setRepositoryId(viewFilters.repositoryId ?? "");
    setScanner(viewFilters.scanner ?? "");
    setSearch(viewFilters.search ?? "");
    setPage(0);
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Page header */}
      <PageHeader
        eyebrow="Triage"
        title="Security Findings"
        description="Review, filter, and bulk-manage the normalized findings detected across repositories in this project."
        actions={
          <Button onClick={() => handleExportFiltered("csv")}>
            <Download className="h-4 w-4" />
            Download Report
          </Button>
        }
      />

      {/* Bulk action bar */}
      {selected.length > 0 && (
        <div className="card-serif mb-4 flex items-center gap-3 px-4 py-3 animate-fade-up">
          <Badge variant="primary" className="text-xs">
            {selected.length} selected
          </Badge>
          <Button size="sm" onClick={handleBulkResolve} className="gap-1.5">
            Resolve
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleSuppress("Bulk suppressed")}
            className="gap-1.5"
          >
            Suppress
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              handleBulkTriage(
                "accept_risk",
                "Bulk accepted risk from findings page"
              )
            }
            className="gap-1.5"
          >
            Accept Risk
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              handleBulkTriage(
                "mark_duplicate",
                "Bulk marked duplicate from findings page"
              )
            }
            className="gap-1.5"
          >
            Duplicate
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSelected([])}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Filter bar */}
      <FilterBar
        className="mb-6"
        searchValue={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(0);
        }}
        searchPlaceholder="Search findings, repositories..."
        filters={[
          {
            key: "severity",
            label: "Severity",
            value: severity,
            onChange: (value) => {
              setSeverity(value);
              setPage(0);
            },
            options: SEVERITIES.map((s) => ({ value: s, label: s.charAt(0).toUpperCase() + s.slice(1) })),
          },
          {
            key: "status",
            label: "Status",
            value: status,
            onChange: (value) => {
              setStatus(value);
              setPage(0);
            },
            options: STATUSES.map((s) => ({
              value: s,
              label: s.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
            })),
          },
          {
            key: "repository",
            label: "Repository",
            value: repositoryId,
            onChange: (value) => {
              setRepositoryId(value);
              setPage(0);
            },
            options: repos.map((r: any) => ({ value: r.id, label: r.full_name })),
          },
          {
            key: "category",
            label: "Category",
            value: category,
            onChange: (value) => {
              setCategory(value);
              setPage(0);
            },
            options: CATEGORIES.map((c) => ({
              value: c,
              label: c.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
            })),
          },
        ]}
        onClearAll={isActive ? clearAllFilters : undefined}
      />

      {/* Saved view bar */}
      <FindingsSavedViewBar
        filters={filters}
        onSaveView={handleSaveView}
        savedViews={savedViews}
        onApplyView={handleApplyView}
      />

      {/* Table area */}
      {loading ? (
        <SkeletonTable rows={8} />
      ) : findings.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No findings found"
          description="Try adjusting your filters or run a new scan"
        />
      ) : (
        <>
          <div className="card-serif overflow-hidden">
            <FindingsTable
              findings={sortedFindings}
              repos={repos}
              selected={selected}
              onToggleSelect={toggleSelect}
              onToggleAll={toggleAll}
              onSelectFinding={setSelectedFinding}
              sortBy={sortBy}
              sortDir={sortDir}
              onSort={toggleSort}
              focusedIndex={focusedIndex}
            />
          </div>

          <Pagination
            page={page}
            total={total}
            limit={limit}
            onPageChange={setPage}
          />
        </>
      )}

      {/* Finding detail drawer */}
      {selectedFinding && (
        <FindingDrawer
          orgId={org_id as string}
          projectId={project_id as string}
          findingId={selectedFinding}
          onClose={() => setSelectedFinding(null)}
          onUpdate={fetchFindings}
          onSelectFinding={(id) => setSelectedFinding(id)}
        />
      )}
    </div>
  );
}

// ─── Page export ──────────────────────────────────────────────────────────────

export default function FindingsPage() {
  return (
    <Suspense fallback={<div />}>
      <FindingsContent />
    </Suspense>
  );
}
