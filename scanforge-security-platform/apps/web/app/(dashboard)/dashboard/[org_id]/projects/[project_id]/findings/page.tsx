"use client";

import { Suspense, useEffect, useState, useCallback, useRef } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Search, List, Layers, Download, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonTable } from "@/components/scanforge/loading-skeleton";
import { FindingsTable } from "@/components/scanforge/findings-table";
import { FilterBar } from "@/components/scanforge/filter-bar";
import { SeverityBadge } from "@/components/scanforge/severity-badge";
import { StatusBadge } from "@/components/scanforge/status-badge";
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

function findingAge(firstSeenAt: string): { label: string; color: string } {
  const days = Math.floor(
    (Date.now() - new Date(firstSeenAt).getTime()) / 86400000
  );
  if (days <= 7) return { label: `${days}d`, color: "text-success" };
  if (days <= 30) return { label: `${days}d`, color: "text-warning" };
  if (days <= 90) return { label: `${days}d`, color: "text-warning" };
  return { label: `${days}d`, color: "text-danger" };
}

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
  const [viewMode, setViewMode] = useState<"flat" | "grouped">("flat");
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const limit = 30;

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

  const groupedFindings = sortedFindings.reduce(
    (acc: Record<string, any[]>, f: any) => {
      const key = f.category;
      if (!acc[key]) acc[key] = [];
      acc[key].push(f);
      return acc;
    },
    {}
  );

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

  return (
    <div>
      <PageHeader
        title="Findings"
        description={`${total} findings across all repositories`}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleExportFiltered("csv")}
              className="gap-1.5"
            >
              <Download className="h-3.5 w-3.5" /> CSV
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleExportFiltered("json")}
              className="gap-1.5"
            >
              <Download className="h-3.5 w-3.5" /> JSON
            </Button>
          </div>
        }
      />

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

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <FilterBar
          searchValue={search}
          onSearchChange={(v) => {
            setSearch(v);
            setPage(0);
          }}
          searchPlaceholder="Search findings..."
          filters={[
            {
              key: "severity",
              label: "All Severities",
              options: SEVERITIES.map((s) => ({
                value: s,
                label: s.charAt(0).toUpperCase() + s.slice(1),
              })),
              value: severity,
              onChange: (v) => {
                setSeverity(v);
                setPage(0);
              },
            },
            {
              key: "category",
              label: "All Categories",
              options: CATEGORIES.map((c) => ({
                value: c,
                label: c.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
              })),
              value: category,
              onChange: (v) => {
                setCategory(v);
                setPage(0);
              },
            },
            {
              key: "status",
              label: "All Statuses",
              options: STATUSES.map((s) => ({
                value: s,
                label: s.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase()),
              })),
              value: status,
              onChange: (v) => {
                setStatus(v);
                setPage(0);
              },
            },
            {
              key: "repositoryId",
              label: "All Repositories",
              options: repos.map((r: any) => ({
                value: r.id,
                label: r.full_name,
              })),
              value: repositoryId,
              onChange: (v) => {
                setRepositoryId(v);
                setPage(0);
              },
            },
            {
              key: "scanner",
              label: "All Scanners",
              options: [
                { value: "trivy", label: "Trivy" },
                { value: "gitleaks", label: "Gitleaks" },
                { value: "osv", label: "OSV-Scanner" },
              ],
              value: scanner,
              onChange: (v) => {
                setScanner(v);
                setPage(0);
              },
            },
          ]}
          onClearAll={
            hasActiveFilters
              ? () => {
                  setSeverity("");
                  setCategory("");
                  setStatus("");
                  setSearch("");
                  setRepositoryId("");
                  setScanner("");
                  setPage(0);
                }
              : undefined
          }
          className="flex-1"
        />

        <div className="flex items-center rounded-lg border border-border bg-surface p-0.5">
          <button
            onClick={() => setViewMode("flat")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              viewMode === "flat"
                ? "bg-surface-elevated text-text-primary shadow-sm"
                : "text-text-tertiary hover:text-text-secondary"
            )}
          >
            <List className="h-3.5 w-3.5" /> List
          </button>
          <button
            onClick={() => setViewMode("grouped")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              viewMode === "grouped"
                ? "bg-surface-elevated text-text-primary shadow-sm"
                : "text-text-tertiary hover:text-text-secondary"
            )}
          >
            <Layers className="h-3.5 w-3.5" /> Grouped
          </button>
        </div>
      </div>

      {loading ? (
        <SkeletonTable rows={8} />
      ) : findings.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No findings found"
          description="Try adjusting your filters or run a new scan"
        />
      ) : viewMode === "flat" ? (
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
          <div className="flex items-center justify-between px-2 py-4 mt-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <span className="text-xs text-text-tertiary font-mono">
              {page * limit + 1}–{Math.min((page + 1) * limit, total)} of{" "}
              {total}
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={(page + 1) * limit >= total}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </>
      ) : (
        <>
          {Object.entries(groupedFindings).map(([cat, items]) => (
            <div key={cat} className="mb-6 animate-fade-up">
              <h4 className="flex items-center gap-2 mb-3 text-sm font-semibold font-display text-text-primary capitalize">
                {cat.replace(/_/g, " ")}
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                  {(items as any[]).length}
                </Badge>
              </h4>
              <div className="rounded-xl border border-border bg-surface overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent border-b border-border">
                      <TableHead className="w-10">
                        <Checkbox
                          checked={
                            selected.length === sortedFindings.length &&
                            sortedFindings.length > 0
                          }
                          onCheckedChange={toggleAll}
                          aria-label="Select all"
                        />
                      </TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Repository</TableHead>
                      <TableHead>First Seen</TableHead>
                      <TableHead>Age</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(items as any[]).map((f) => {
                      const age = findingAge(f.first_seen_at);
                      return (
                        <TableRow
                          key={f.id}
                          className={cn(
                            "cursor-pointer transition-colors",
                            selected.includes(f.id) && "bg-primary/[0.03]"
                          )}
                        >
                          <TableCell>
                            <Checkbox
                              checked={selected.includes(f.id)}
                              onCheckedChange={() => toggleSelect(f.id)}
                              aria-label={`Select finding`}
                            />
                          </TableCell>
                          <TableCell>
                            <SeverityBadge severity={f.severity} />
                          </TableCell>
                          <TableCell>
                            <button
                              onClick={() => setSelectedFinding(f.id)}
                              className="text-left text-sm text-text-primary hover:text-primary transition-colors font-medium truncate max-w-[300px] block"
                            >
                              {f.title}
                            </button>
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={f.status} showIcon={false} />
                          </TableCell>
                          <TableCell>
                            <span className="font-mono text-xs text-text-tertiary">
                              {f.repository_id?.slice(0, 8)}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className="text-xs text-text-tertiary">
                              {new Date(f.first_seen_at).toLocaleDateString()}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span
                              className={cn(
                                "text-xs font-medium font-mono",
                                age.color
                              )}
                            >
                              {age.label}
                            </span>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </div>
          ))}
        </>
      )}

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

export default function FindingsPage() {
  return (
    <Suspense fallback={<div />}>
      <FindingsContent />
    </Suspense>
  );
}
