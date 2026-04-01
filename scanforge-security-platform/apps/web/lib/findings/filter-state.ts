export interface FindingsFilters {
  severity?: string;
  status?: string;
  category?: string;
  repositoryId?: string;
  scanner?: string;
  search?: string;
}

export function serializeFindingsFilters(filters: FindingsFilters): Record<string, string> {
  const result: Record<string, string> = {};
  if (filters.severity) result.severity = filters.severity;
  if (filters.status) result.status = filters.status;
  if (filters.category) result.category = filters.category;
  if (filters.repositoryId) result.repositoryId = filters.repositoryId;
  if (filters.scanner) result.scanner = filters.scanner;
  if (filters.search) result.search = filters.search;
  return result;
}

export function parseFindingsFilters(params: URLSearchParams): FindingsFilters {
  return {
    severity: params.get("severity") ?? undefined,
    status: params.get("status") ?? undefined,
    category: params.get("category") ?? undefined,
    repositoryId: params.get("repositoryId") ?? undefined,
    scanner: params.get("scanner") ?? undefined,
    search: params.get("search") ?? undefined,
  };
}

export function hasActiveFilters(filters: FindingsFilters): boolean {
  return !!(filters.severity || filters.status || filters.category || filters.repositoryId || filters.scanner || filters.search);
}

export function buildSavedViewPayload(filters: FindingsFilters, name: string): { name: string; filters: Record<string, string> } {
  return { name, filters: serializeFindingsFilters(filters) };
}

export function getRepoDisplayName(repo: { full_name?: string; repo_name?: string; id: string }): string {
  return repo.full_name ?? repo.repo_name ?? repo.id.slice(0, 8);
}

export function formatExportScope(filters: FindingsFilters, total: number): string {
  const parts: string[] = [];
  if (filters.severity) parts.push(`severity: ${filters.severity}`);
  if (filters.status) parts.push(`status: ${filters.status}`);
  if (filters.category) parts.push(`category: ${filters.category}`);
  if (filters.repositoryId) parts.push(`repository: ${filters.repositoryId}`);
  if (parts.length === 0) return `All ${total} findings`;
  return `${parts.join(", ")} — ${total} findings`;
}
