"use client";

import { useState, useEffect } from "react";
import { Calendar, Plus, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface Props {
  orgId: string;
  projectId: string;
  repoId: string;
  repoName: string;
}

export default function ScheduleSection({ orgId, projectId, repoId, repoName }: Props) {
  const [schedules, setSchedules] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ schedule_type: "daily", scan_type: "full", cron_expression: "" });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.schedules.list(orgId, projectId, repoId)
      .then((data: any) => { setSchedules(Array.isArray(data) ? data : (data?.items ?? [])); setLoading(false); })
      .catch(() => setLoading(false));
  }, [repoId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const sched = await api.schedules.create(orgId, projectId, repoId, {
        repository_id: repoId,
        ...form,
        cron_expression: form.cron_expression || undefined,
      });
      setSchedules((prev) => [...prev, sched]);
      setShowCreate(false);
      setForm({ schedule_type: "daily", scan_type: "full", cron_expression: "" });
    } catch (err) { console.error(err); }
  };

  const toggleActive = async (sched: any) => {
    try {
      const updated = await api.schedules.update(orgId, projectId, repoId, sched.id, { is_active: !sched.is_active });
      setSchedules((prev) => prev.map((s) => s.id === sched.id ? updated : s));
    } catch (err) { console.error(err); }
  };

  const handleDelete = async (schedId: string) => {
    try {
      await api.schedules.remove(orgId, projectId, repoId, schedId);
      setSchedules((prev) => prev.filter((s) => s.id !== schedId));
    } catch (err) { console.error(err); }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold font-display text-text-primary flex items-center gap-2">
          <Calendar className="h-4 w-4" /> Schedules for {repoName}
        </h4>
        <Button variant="outline" size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-3.5 w-3.5 mr-1" /> Add
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-text-tertiary py-4">Loading schedules\u2026</p>
      ) : schedules.length === 0 && !showCreate ? (
        <p className="text-sm text-text-tertiary py-4">No scan schedules configured</p>
      ) : (
        <div className="space-y-2">
          {schedules.map((sched) => (
            <div key={sched.id} className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
              <button
                className="text-text-tertiary hover:text-text-primary transition-colors"
                onClick={() => toggleActive(sched)}
                title={sched.is_active ? "Disable" : "Enable"}
              >
                {sched.is_active
                  ? <ToggleRight className="h-5 w-5 text-success" />
                  : <ToggleLeft className="h-5 w-5" />
                }
              </button>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-text-primary capitalize">
                  {sched.schedule_type.replace(/_/g, " ")}
                </span>
                {sched.cron_expression && (
                  <code className="ml-2 font-mono text-xs text-text-tertiary bg-surface-elevated rounded px-1.5 py-0.5">
                    {sched.cron_expression}
                  </code>
                )}
                <span className="ml-2 text-xs text-text-tertiary">Scan: {sched.scan_type}</span>
              </div>
              {sched.next_run_at && (
                <span className="text-xs text-text-tertiary">Next: {new Date(sched.next_run_at).toLocaleString()}</span>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-text-tertiary hover:text-danger"
                onClick={() => handleDelete(sched.id)}
                title="Delete schedule"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="mt-3 rounded-lg border border-border bg-surface p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Schedule</Label>
              <Select value={form.schedule_type} onValueChange={(val) => setForm({ ...form, schedule_type: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Daily</SelectItem>
                  <SelectItem value="weekly">Weekly</SelectItem>
                  <SelectItem value="on_push">On Push</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Scan Type</Label>
              <Select value={form.scan_type} onValueChange={(val) => setForm({ ...form, scan_type: val })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="full">Full Scan</SelectItem>
                  <SelectItem value="dependencies">Dependencies</SelectItem>
                  <SelectItem value="secrets">Secrets</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {form.schedule_type !== "on_push" && (
            <div className="space-y-2">
              <Label>Cron (optional)</Label>
              <Input
                placeholder="Cron expression"
                value={form.cron_expression}
                onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
              />
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button type="submit">Create</Button>
          </div>
        </form>
      )}
    </div>
  );
}
