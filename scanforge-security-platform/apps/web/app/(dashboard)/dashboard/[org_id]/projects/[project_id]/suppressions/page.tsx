"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Shield, Plus, ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/scanforge/page-header";
import { EmptyState } from "@/components/scanforge/empty-state";
import { SkeletonList } from "@/components/scanforge/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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

const RULE_TYPES = ["category", "severity", "path", "scanner"];
const SEVERITIES = ["critical", "high", "medium", "low", "info"];

export default function SuppressionsPage() {
  const { org_id, project_id } = useParams<{ org_id: string; project_id: string }>();
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    rule_type: "severity",
    match_key: "severity",
    match_value: "low",
    reason: "",
    scope: "project",
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.suppressionRules.list(org_id as string).then((res: any) => {
      setRules(res.items ?? []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [org_id]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const matchCriteria: Record<string, string> = {};
      matchCriteria[form.match_key] = form.match_value;
      const data: any = {
        rule_type: form.rule_type,
        match_criteria_json: matchCriteria,
        reason: form.reason,
      };
      if (form.scope === "project") data.project_id = project_id;
      const rule = await api.suppressionRules.create(org_id as string, data);
      setRules((prev) => [rule, ...prev]);
      setShowCreate(false);
      setForm({ rule_type: "severity", match_key: "severity", match_value: "low", reason: "", scope: "project" });
    } catch {} finally { setCreating(false); }
  }

  const toggleActive = async (rule: any) => {
    try {
      const updated = await api.suppressionRules.update(org_id as string, rule.id, { is_active: !rule.is_active });
      setRules((prev) => prev.map((r) => r.id === rule.id ? updated : r));
    } catch {}
  };

  const handleDelete = async (ruleId: string) => {
    try {
      await api.suppressionRules.remove(org_id as string, ruleId);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
    } catch {}
  };

  return (
    <div>
      <PageHeader
        title="Suppression Rules"
        description="Manage global suppression rules for findings"
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-1" /> Create Rule
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
                <SelectContent>
                  {RULE_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                </SelectContent>
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
                  <SelectContent>
                    {SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  value={form.match_value}
                  onChange={(e) => setForm({ ...form, match_value: e.target.value })}
                  placeholder="e.g. secret, vulnerability"
                />
              )}
            </div>
            <div className="space-y-2">
              <Label>Reason</Label>
              <Textarea
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="Why is this rule needed?"
                rows={2}
              />
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
        <EmptyState
          icon={Shield}
          title="No suppression rules"
          description="Create rules to suppress findings across your organization"
        />
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div key={rule.id} className="flex items-center gap-3 rounded-xl border border-border bg-surface p-4">
              <button
                className="text-text-tertiary hover:text-text-primary transition-colors flex-shrink-0"
                onClick={() => toggleActive(rule)}
              >
                {rule.is_active
                  ? <ToggleRight className="h-5 w-5 text-success" />
                  : <ToggleLeft className="h-5 w-5" />
                }
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-xs">{rule.rule_type}</Badge>
                  <code className="font-mono text-xs text-text-tertiary bg-surface-elevated rounded px-1.5 py-0.5">
                    {JSON.stringify(rule.match_criteria_json)}
                  </code>
                </div>
                <div className="text-sm text-text-secondary">{rule.reason}</div>
                <div className="flex items-center gap-3 mt-1 text-xs text-text-tertiary">
                  {rule.project_id && <span>Project-scoped</span>}
                  {rule.created_at && <span>{new Date(rule.created_at).toLocaleDateString()}</span>}
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-text-tertiary hover:text-danger flex-shrink-0"
                onClick={() => handleDelete(rule.id)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
