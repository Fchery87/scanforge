"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Plus, Shield, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";

import { api } from "@/lib/api";
import { EmptyState } from "@/components/scanforge/empty-state";
import { PageHeader } from "@/components/scanforge/page-header";
import { SkeletonList } from "@/components/scanforge/loading-skeleton";
import { Badge } from "@/components/ui/badge";
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
import { Textarea } from "@/components/ui/textarea";

const RULE_TYPES = ["category", "severity", "path", "scanner"];
const SEVERITIES = ["critical", "high", "medium", "low", "info"];

export default function SuppressionsPage() {
  const { org_id, project_id } = useParams<{ org_id: string; project_id: string }>();
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ rule_type: "severity", match_key: "severity", match_value: "low", reason: "", scope: "project" });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.suppressionRules.list(org_id as string)
      .then((res: any) => {
        setRules(res.items ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [org_id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const matchCriteria: Record<string, string> = { [form.match_key]: form.match_value };
      const data: any = { rule_type: form.rule_type, match_criteria_json: matchCriteria, reason: form.reason };
      if (form.scope === "project") data.project_id = project_id;
      const created = await api.suppressionRules.create(org_id as string, data);
      setRules((current) => [created, ...current]);
      setShowCreate(false);
      setForm({ rule_type: "severity", match_key: "severity", match_value: "low", reason: "", scope: "project" });
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(rule: any) {
    try {
      const updated = await api.suppressionRules.update(org_id as string, rule.id, { is_active: !rule.is_active });
      setRules((current) => current.map((entry) => entry.id === rule.id ? updated : entry));
    } catch {}
  }

  async function handleDelete(ruleId: string) {
    try {
      await api.suppressionRules.remove(org_id as string, ruleId);
      setRules((current) => current.filter((rule) => rule.id !== ruleId));
    } catch {}
  }

  return (
    <div>
      <PageHeader
        eyebrow="Governance"
        title="Suppression Rules"
        description="Manage rules that intentionally suppress classes of findings at project or organization scope."
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            Create Rule
          </Button>
        }
      />

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Suppression Rule</DialogTitle>
            <DialogDescription>Define a rule to suppress matching findings.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Rule Type</Label>
              <Select value={form.rule_type} onValueChange={(val) => setForm({ ...form, rule_type: val, match_key: val === "category" ? "category" : "severity" })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{RULE_TYPES.map((type) => <SelectItem key={type} value={type}>{type}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Match On</Label>
              <Select value={form.match_key} onValueChange={(val) => setForm({ ...form, match_key: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="severity">Severity</SelectItem>
                  <SelectItem value="category">Category</SelectItem>
                  <SelectItem value="scanner">Scanner</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Match Value</Label>
              {form.match_key === "severity" ? (
                <Select value={form.match_value} onValueChange={(val) => setForm({ ...form, match_value: val })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{SEVERITIES.map((severity) => <SelectItem key={severity} value={severity}>{severity}</SelectItem>)}</SelectContent>
                </Select>
              ) : (
                <Input value={form.match_value} onChange={(e) => setForm({ ...form, match_value: e.target.value })} placeholder="e.g. secret, vulnerability" />
              )}
            </div>
            <div className="space-y-2">
              <Label>Reason</Label>
              <Textarea value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="Why is this rule needed?" rows={2} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" disabled={creating || !form.reason}>{creating ? "Creating..." : "Create Rule"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {loading ? (
        <SkeletonList rows={5} />
      ) : rules.length === 0 ? (
        <EmptyState icon={Shield} title="No suppression rules" description="Create rules to suppress findings across your organization." />
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div key={rule.id} className="card-serif flex items-center gap-4 p-4">
              <button className="text-text-tertiary transition-colors hover:text-text-primary" onClick={() => toggleActive(rule)}>
                {rule.is_active ? <ToggleRight className="h-6 w-6 text-success" /> : <ToggleLeft className="h-6 w-6" />}
              </button>
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{rule.rule_type}</Badge>
                  <code className="rounded-[6px] border border-border bg-background px-2 py-1 font-mono text-[11px] text-text-tertiary">
                    {JSON.stringify(rule.match_criteria_json)}
                  </code>
                </div>
                <p className="text-sm text-text-secondary">{rule.reason}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-text-tertiary">
                  {rule.project_id ? <span>Project-scoped</span> : <span>Organization-scoped</span>}
                  {rule.created_at ? <span>{new Date(rule.created_at).toLocaleDateString()}</span> : null}
                </div>
              </div>
              <Button variant="ghost" size="icon" className="h-9 w-9 text-text-tertiary hover:text-danger" onClick={() => handleDelete(rule.id)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
