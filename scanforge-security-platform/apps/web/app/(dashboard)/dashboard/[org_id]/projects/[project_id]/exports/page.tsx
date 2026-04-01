"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Download, FileText, Plus } from "lucide-react";

import { api } from "@/lib/api";
import { summarizeExportSize } from "@/lib/project-surface";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonList } from "@/components/scanforge/loading-skeleton";
import { StatusBadge } from "@/components/scanforge/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TYPES = ["findings", "pipeline", "summary"];
const FORMATS = ["csv", "json", "pdf"];

export default function ExportsPage() {
  const { org_id, project_id } = useParams();
  const [exportsList, setExportsList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ export_type: "findings", format: "csv", title: "", filters: { severity: "", category: "", status: "" } });
  const [creating, setCreating] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    if (!org_id || !project_id) return;
    api.exports.list(org_id as string, project_id as string)
      .then((res) => {
        setExportsList(res.items ?? []);
        setLoadError("");
        setLoading(false);
      })
      .catch((err: any) => {
        setLoadError(err.message || "Failed to load exports");
        setLoading(false);
      });
  }, [org_id, project_id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError("");
    try {
      const filters = Object.fromEntries(Object.entries(form.filters).filter(([, value]) => value !== ""));
      const created = await api.exports.create(org_id as string, project_id as string, {
        export_type: form.export_type,
        format: form.format,
        title: form.title || undefined,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
      });
      setExportsList((current) => [created, ...current]);
      setShowCreate(false);
      setForm({ export_type: "findings", format: "csv", title: "", filters: { severity: "", category: "", status: "" } });
    } catch (err: any) {
      setCreateError(err.message || "Failed to generate export");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Reports"
        title="Exports"
        description="Generate downloadable findings, pipeline, and summary reports for audit, remediation, and sharing."
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            New Export
          </Button>
        }
      />

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate Export</DialogTitle>
            <DialogDescription>Configure and generate a new data export.</DialogDescription>
          </DialogHeader>
          {createError ? <p className="text-sm text-danger">{createError}</p> : null}
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Export Type</Label>
              <Select value={form.export_type} onValueChange={(val) => setForm({ ...form, export_type: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{TYPES.map((type) => <SelectItem key={type} value={type}>{type}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Format</Label>
              <Select value={form.format} onValueChange={(val) => setForm({ ...form, format: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{FORMATS.map((format) => <SelectItem key={format} value={format}>{format.toUpperCase()}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Title (optional)</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Q1 Security Report" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating}>{creating ? "Generating..." : "Generate"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {loading ? (
        <SkeletonList rows={5} />
      ) : loadError ? (
        <EmptyState icon={FileText} title="Exports unavailable" description={loadError} />
      ) : exportsList.length === 0 ? (
        <EmptyState icon={FileText} title="No exports yet" description="Generate your first export to download findings data." />
      ) : (
        <div className="space-y-3">
          {exportsList.map((exp) => {
            const size = summarizeExportSize(exp.size_bytes);
            return (
              <div key={exp.id} className="card-serif flex items-center gap-4 p-4">
                <div className="flex h-11 w-11 items-center justify-center rounded-[10px] border border-border bg-background text-primary">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-text-primary">{exp.title ?? `${exp.export_type} export`}</p>
                  <p className="mt-1 text-xs text-text-tertiary">
                    {exp.format.toUpperCase()} · {exp.export_type} · {new Date(exp.created_at).toLocaleString()}
                    {exp.row_count != null ? ` · ${exp.row_count} rows` : ""}
                    {size ? ` · ${size}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={exp.status} />
                  {exp.status === "completed" && exp.storage_uri ? (
                    <a href={exp.storage_uri} target="_blank" rel="noopener noreferrer">
                      <Button variant="ghost" size="sm">
                        <Download className="h-4 w-4" />
                        Download
                      </Button>
                    </a>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
