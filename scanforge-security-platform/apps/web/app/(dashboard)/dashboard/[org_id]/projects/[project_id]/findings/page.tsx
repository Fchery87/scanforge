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
import FindingDrawer from "./FindingDrawer";

const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const CATEGORIES = [
  "vulnerability",
  "secret",
  "dependency_outdated",
  "malicious_pattern",
  "code_quality",
];
const STATUSES = ["open", "fixed", "suppressed", "accepted_risk", "duplicate"];

// ─── Filter Pill ─────────────────────────────────────────────────────────────

interface FilterPillProps {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}

function FilterPill({ label, value, options, onChange }: FilterPillProps) {
  const isActive = value !== "";
  const activeOption = options.find((o) => o.value === value);
  const displayLabel = activeOption ? activeOption.label : label;

  return (
    <div className="relative">
      <div
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
          isActive
            ? "border-primary/30 bg-primary/5 text-primary"
            : "border-border bg-surface text-text-secondary hover:border-border-strong hover:text-text-primary"
        )}
      >
        <ChevronRight
          className={cn(
            "h-3 w-3 rotate-90 transition-colors",
            isActive ? "text-primary/70" : "text-text-tertiary"
          )}
        />
        <span>{displayLabel}</span>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          aria-label={label}
        >
          <option value="">{label}</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

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
  const searchParams = useSearchParams();
  const router = useRouter();

  const [findings, setFindings] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<string | null>(null);
  const [severity, setSeverity] = useState(searchParams.get("severity") ?? "");
  const [category, setCategory] = useState(searchParams.get("category") ?? "");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [repositoryId, setRepositoryId] = useState(
    searchParams.get("repositoryId") ?? ""
  );
  const [scanner, setScanner] = useState(searchParams.get("scanner") ?? "");
  const [repos, setRepos] = useState<any[]>([]);
  const [sortBy, setSortBy] = useState<string>("first_seen_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const limit = 30;

  // ── URL sync ────────────────────────────────────────────────────────────────
  const updateUrl = useCallback(
    (overrides?: Record<string, string>) => {
      const params = new URLSearchParams();
      if (severity) params.set("severity", severity);
      if (category) params.set("category", category);
      if (repositoryId) params.set("repositoryId", repositoryId);
      if (scanner) params.set("scanner", scanner);
      if (overrides) {
        Object.entries(overrides).forEach(([k, v]) => {
          if (v) params.set(k, v);
          else params.delete(k);
        });
      }
      const qs = params.toString();
      router.push(`?${qs}`, { scroll: false });
    },
    [severity, category, repositoryId, scanner, router]
  );

  // ── Data fetching ───────────────────────────────────────────────────────────
  const fetchFindings = useCallback(async () => {
    setLoading(true);
    const params: Record<string, string> = {
      skip: String(page * limit),
      limit: String(limit),
    };
    if (severity) params.severity = severity;
    if (category) params.category = category;
    if (status) params.status = status;
    if (search) params.search = search;
    if (repositoryId) params.repository_id = repositoryId;
    if (scanner) params.scanner = scanner;
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
    } catch {}
  }, [org_id, project_id]);

  useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  useEffect(() => {
    fetchRepos();
  }, [fetchRepos]);

  useEffect(() => {
    const s = searchParams.get("severity") ?? "";
    const c = searchParams.get("category") ?? "";
    const r = searchParams.get("repositoryId") ?? "";
    const sc = searchParams.get("scanner") ?? "";
    if (s !== severity) setSeverity(s);
    if (c !== category) setCategory(c);
    if (r !== repositoryId) setRepositoryId(r);
    if (sc !== scanner) setScanner(sc);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

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
    }
    return sortDir === "asc" ? cmp : -cmp;
  });

  const sortedFindingsRef = useRef(sortedFindings);
  sortedFindingsRef.current = sortedFindings;

  // ── Bulk actions ────────────────────────────────────────────────────────────
  const handleBulkResolve = async () => {
    if (selected.length === 0) return;
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

  const handleExportFiltered = async (format: "csv" | "json") => {
    const params = Object.fromEntries(searchParams.entries());
    try {
      await api.exports.create(org_id as string, project_id as string, {
        export_type: "findings",
        format,
        title: `Filtered findings - ${new Date().toISOString().slice(0, 10)}`,
        filters: params,
      });
      alert(`Export started. Check the Exports page for download.`);
    } catch (err) {
      console.error(err);
    }
  };

  const hasActiveFilters =
    severity || category || status || search || repositoryId || scanner;

  const clearAllFilters = () => {
    setSeverity("");
    setCategory("");
    setStatus("");
    setSearch("");
    setRepositoryId("");
    setScanner("");
    setPage(0);
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Page header */}
      <PageHeader
        title="Security Findings Inventory"
        description="Manage your team's security issues and vulnerabilities across repositories."
      />

      {/* Bulk action bar */}
      {selected.length > 0 && (
        <div className="flex items-center gap-3 mb-4 px-4 py-2.5 rounded-xl border border-border bg-surface animate-fade-up">
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
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {/* Search input */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-tertiary pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Search findings, repositories..."
            className="w-full rounded-full border border-border bg-surface pl-9 pr-4 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary outline-none transition-colors focus:border-primary/50 focus:ring-1 focus:ring-primary/30"
          />
        </div>

        {/* Severity filter */}
        <FilterPill
          label="Severity (All)"
          value={severity}
          options={SEVERITIES.map((s) => ({
            value: s,
            label: s.charAt(0).toUpperCase() + s.slice(1),
          }))}
          onChange={(v) => {
            setSeverity(v);
            setPage(0);
          }}
        />

        {/* Status filter */}
        <FilterPill
          label="Status (Open)"
          value={status}
          options={STATUSES.map((s) => ({
            value: s,
            label: s
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase()),
          }))}
          onChange={(v) => {
            setStatus(v);
            setPage(0);
          }}
        />

        {/* Repository filter */}
        <FilterPill
          label="Repository (All)"
          value={repositoryId}
          options={repos.map((r: any) => ({
            value: r.id,
            label: r.full_name,
          }))}
          onChange={(v) => {
            setRepositoryId(v);
            setPage(0);
          }}
        />

        {/* Category filter (Assignee slot in the design) */}
        <FilterPill
          label="Category (All)"
          value={category}
          options={CATEGORIES.map((c) => ({
            value: c,
            label: c
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase()),
          }))}
          onChange={(v) => {
            setCategory(v);
            setPage(0);
          }}
        />

        {/* Clear filters */}
        {hasActiveFilters && (
          <button
            onClick={clearAllFilters}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-tertiary hover:border-border-strong hover:text-text-secondary transition-colors"
            aria-label="Clear all filters"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Download Report */}
        <button
          onClick={() => handleExportFiltered("csv")}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary/90 active:bg-primary/80 transition-colors"
        >
          <Download className="h-3.5 w-3.5" />
          Download Report
        </button>
      </div>

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
          <FindingsTable
            findings={sortedFindings}
            selected={selected}
            onToggleSelect={toggleSelect}
            onToggleAll={toggleAll}
            onSelectFinding={setSelectedFinding}
            sortBy={sortBy}
            sortDir={sortDir}
            onSort={toggleSort}
            focusedIndex={focusedIndex}
          />

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
