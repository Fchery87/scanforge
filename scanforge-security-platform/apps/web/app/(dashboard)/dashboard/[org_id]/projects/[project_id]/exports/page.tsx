"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { FileText, Download, Plus } from "lucide-react";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { SkeletonList } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const TYPES = ["findings", "pipeline", "summary"];
const FORMATS = ["csv", "json", "pdf", "sarif"];

export default function ExportsPage() {
  const { org_id, project_id } = useParams();
  const [exports, setExports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ export_type: "findings", format: "csv", title: "", filters: { severity: "", category: "", status: "" } });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.exports.list(org_id as string, project_id as string)
      .then((res) => { setExports(res.items ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [org_id, project_id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const filters = Object.fromEntries(
        Object.entries(form.filters).filter(([, v]) => v !== "")
      );
      const exp = await api.exports.create(org_id as string, project_id as string, {
        export_type: form.export_type,
        format: form.format,
        title: form.title || undefined,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
      });
      setExports([exp, ...exports]);
      setShowCreate(false);
      setForm({ export_type: "findings", format: "csv", title: "", filters: { severity: "", category: "", status: "" } });
    } catch {} finally { setCreating(false); }
  }

  return (
    <div>
      <PageHeader
        title="Exports"
        description="Download findings, reports and scan data"
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-1" /> New Export
          </Button>
        }
      />

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Export</DialogTitle>
            <DialogDescription>Configure and generate a new data export.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Export Type</Label>
              <Select value={form.export_type} onValueChange={(val) => setForm({ ...form, export_type: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Format</Label>
              <Select value={form.format} onValueChange={(val) => setForm({ ...form, format: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {FORMATS.map((f) => <SelectItem key={f} value={f}>{f.toUpperCase()}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Title (optional)</Label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Q1 Security Report"
              />
            </div>
            {form.export_type === "findings" && (
              <>
                <div className="space-y-2">
                  <Label>Severity Filter (optional)</Label>
                  <Select value={form.filters.severity} onValueChange={(val) => setForm({ ...form, filters: { ...form.filters, severity: val } })}>
                    <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Category Filter (optional)</Label>
                  <Select value={form.filters.category} onValueChange={(val) => setForm({ ...form, filters: { ...form.filters, category: val } })}>
                    <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All</SelectItem>
                      <SelectItem value="vulnerability">Vulnerability</SelectItem>
                      <SelectItem value="secret">Secret</SelectItem>
                      <SelectItem value="dependency_outdated">Dependency</SelectItem>
                      <SelectItem value="malicious_pattern">Malicious Pattern</SelectItem>
                      <SelectItem value="code_quality">Code Quality</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Status Filter (optional)</Label>
                  <Select value={form.filters.status} onValueChange={(val) => setForm({ ...form, filters: { ...form.filters, status: val } })}>
                    <SelectTrigger><SelectValue placeholder="All" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All</SelectItem>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="fixed">Fixed</SelectItem>
                      <SelectItem value="suppressed">Suppressed</SelectItem>
                      <SelectItem value="accepted_risk">Accepted Risk</SelectItem>
                      <SelectItem value="duplicate">Duplicate</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>{creating ? "Generating..." : "Generate"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {loading ? (
        <SkeletonList rows={5} />
      ) : exports.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No exports yet"
          description="Generate your first export to download findings data"
        />
      ) : (
        <div className="space-y-2">
          {exports.map((exp) => (
            <div key={exp.id} className="flex items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-elevated">
                  <FileText className="h-5 w-5 text-text-secondary" />
                </div>
                <div className="min-w-0">
                  <div className="font-medium text-text-primary truncate">{exp.title ?? `${exp.export_type} export`}</div>
                  <div className="text-xs text-text-tertiary">
                    {exp.format.toUpperCase()} · {exp.export_type} · {new Date(exp.created_at).toLocaleString()}
                    {exp.row_count != null && <span> · {exp.row_count} rows</span>}
                    {exp.size_bytes > 0 && <span> · {(exp.size_bytes / 1024).toFixed(1)} KB</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <StatusBadge status={exp.status} />
                {exp.expires_at && (
                  <span className={cn(
                    "text-xs",
                    new Date(exp.expires_at) < new Date(Date.now() + 86400000 * 3) ? "text-warning" : "text-text-tertiary"
                  )}>
                    Expires {new Date(exp.expires_at).toLocaleDateString()}
                  </span>
                )}
                {exp.status === "completed" && exp.storage_uri && (
                  <a href={exp.storage_uri} target="_blank" rel="noopener noreferrer">
                    <Button variant="ghost" size="sm">
                      <Download className="h-4 w-4 mr-1" /> Download
                    </Button>
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
