"use client";

import { useState, useEffect } from "react";
import {
  X,
  ExternalLink,
  Clock,
  Shield,
  FileText,
  AlertTriangle,
  CheckCircle,
  Ban,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { SeverityBadge } from "@/components/scanforge/severity-badge";
import { StatusBadge } from "@/components/scanforge/status-badge";

interface FindingDrawerProps {
  orgId: string;
  projectId: string;
  findingId: string;
  onClose: () => void;
  onUpdate: () => void;
  onSelectFinding?: (id: string) => void;
}

export default function FindingDrawer({
  orgId,
  projectId,
  findingId,
  onClose,
  onUpdate,
  onSelectFinding,
}: FindingDrawerProps) {
  const [finding, setFinding] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<string>("details");
  const [related, setRelated] = useState<any[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [actionForm, setActionForm] = useState({
    action: "",
    reason: "",
    fixedVersion: "",
  });
  const [triageForm, setTriageForm] = useState({
    assigneeUserId: "",
    dueDate: "",
  });
  const [acting, setActing] = useState(false);
  const [savingTriage, setSavingTriage] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.findings
      .get(orgId, projectId, findingId)
      .then((data) => {
        setFinding(data);
        setTriageForm({
          assigneeUserId: data.assignee_user_id ?? "",
          dueDate: data.due_date ?? "",
        });
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [findingId, orgId, projectId]);

  useEffect(() => {
    api.members
      .list(orgId, 0, 100)
      .then((res: any) => setMembers(res.items ?? []))
      .catch(() => setMembers([]));
  }, [orgId]);

  useEffect(() => {
    if (tab !== "related" || !finding) return;
    api.findings
      .list(orgId, projectId, {
        category: finding.category,
        repositoryId: finding.repository_id,
      })
      .then((res: any) => {
        setRelated(
          (res.items ?? [])
            .filter((f: any) => f.id !== findingId)
            .slice(0, 5)
        );
      })
      .catch(() => setRelated([]));
  }, [tab, finding, orgId, projectId, findingId]);

  const handleAction = async (action: string) => {
    if (!actionForm.reason && action !== "reopen") return;
    setActing(true);
    try {
      if (action === "suppress") {
        await api.findings.suppress(
          orgId,
          projectId,
          findingId,
          actionForm.reason
        );
      } else if (action === "resolve") {
        await api.findings.resolve(
          orgId,
          projectId,
          findingId,
          actionForm.fixedVersion
        );
      } else if (action === "accept_risk") {
        await api.findings.acceptRisk(
          orgId,
          projectId,
          findingId,
          actionForm.reason
        );
      } else if (action === "mark_duplicate") {
        await api.findings.markDuplicate(
          orgId,
          projectId,
          findingId,
          actionForm.reason
        );
      } else if (action === "reopen") {
        await api.findings.reopen(orgId, projectId, findingId);
      }
      onUpdate();
      const updated = await api.findings.get(orgId, projectId, findingId);
      setFinding(updated);
      setActionForm({ action: "", reason: "", fixedVersion: "" });
    } catch (err) {
      console.error(err);
    } finally {
      setActing(false);
    }
  };

  const handleSaveTriage = async () => {
    setSavingTriage(true);
    try {
      const updated = await api.findings.updateTriage(orgId, projectId, findingId, {
        assignee_user_id: triageForm.assigneeUserId || null,
        due_date: triageForm.dueDate || null,
      });
      setFinding(updated);
      onUpdate();
    } catch (err) {
      console.error(err);
    } finally {
      setSavingTriage(false);
    }
  };

  const formatDate = (d: string) => new Date(d).toLocaleString();

  const daysSince = (d: string) => {
    const days = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
    if (days === 0) return "today";
    if (days === 1) return "1 day ago";
    return `${days} days ago`;
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          "fixed right-0 top-0 bottom-0 z-50 w-full max-w-xl bg-surface border-l border-border shadow-2xl animate-slide-in-right flex flex-col"
        )}
      >
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex items-center gap-2 text-sm text-text-tertiary">
              <div className="h-4 w-4 rounded-full border-2 border-border border-t-primary animate-spin" />
              Loading…
            </div>
          </div>
        ) : !finding ? null : (
          <>
            {/* Header */}
            <div className="flex items-start justify-between p-5 border-b border-border">
              <div className="flex-1 min-w-0 pr-4">
                <div className="flex items-center gap-2 mb-2">
                  <SeverityBadge severity={finding.severity} />
                  <StatusBadge status={finding.status} showIcon={false} />
                </div>
                <h2 className="text-base font-semibold font-display text-text-primary leading-snug">
                  {finding.title}
                </h2>
                <div className="flex items-center gap-3 mt-2 text-xs text-text-tertiary">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    First seen {daysSince(finding.first_seen_at)}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Shield className="h-3 w-3" />
                    {finding.primary_scanner}
                  </span>
                  <span className="capitalize">
                    {finding.category?.replace(/_/g, " ")}
                  </span>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="flex-shrink-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Tabs */}
            <Tabs
              value={tab}
              onValueChange={setTab}
              className="flex-1 flex flex-col min-h-0"
            >
              <div className="px-5 pt-3">
                <TabsList className="w-full">
                  <TabsTrigger value="details" className="flex-1">
                    Details
                  </TabsTrigger>
                  <TabsTrigger value="instances" className="flex-1">
                    Instances ({finding.instances?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="history" className="flex-1">
                    History ({finding.events?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="related" className="flex-1">
                    Related
                  </TabsTrigger>
                </TabsList>
              </div>

              <ScrollArea className="flex-1">
                <TabsContent value="details" className="p-5 space-y-4 mt-0">
                  {finding.description && (
                    <div>
                      <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
                        Description
                      </h4>
                      <p className="text-sm text-text-secondary leading-relaxed">
                        {finding.description}
                      </p>
                    </div>
                  )}

                  {finding.fixed_version && (
                    <>
                      <Separator />
                      <div>
                        <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
                          Remediation
                        </h4>
                        <p className="text-sm text-text-secondary">
                          Upgrade to version{" "}
                          <code className="px-1.5 py-0.5 rounded bg-surface-elevated font-mono text-xs text-primary">
                            {finding.fixed_version}
                          </code>
                        </p>
                      </div>
                    </>
                  )}

                  <Separator />
                  <div className="space-y-3">
                    <div>
                      <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
                        Triage
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <label className="space-y-1.5">
                          <span className="text-[11px] font-medium text-text-tertiary uppercase tracking-wider">
                            Owner
                          </span>
                          <select
                            value={triageForm.assigneeUserId}
                            onChange={(e) =>
                              setTriageForm((prev) => ({
                                ...prev,
                                assigneeUserId: e.target.value,
                              }))
                            }
                            className="h-9 w-full rounded-md border border-border bg-surface-elevated px-3 text-sm text-text-primary outline-none focus:border-primary/50"
                          >
                            <option value="">Unassigned</option>
                            {members.map((member: any) => (
                              <option key={member.user_id} value={member.user_id}>
                                {member.user_name || member.user_email || member.user_id}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="space-y-1.5">
                          <span className="text-[11px] font-medium text-text-tertiary uppercase tracking-wider">
                            Due Date
                          </span>
                          <Input
                            type="date"
                            value={triageForm.dueDate}
                            onChange={(e) =>
                              setTriageForm((prev) => ({
                                ...prev,
                                dueDate: e.target.value,
                              }))
                            }
                            className="h-9 text-sm"
                          />
                        </label>
                      </div>
                    </div>

                    <div className="flex items-center justify-between rounded-lg border border-border bg-surface-elevated px-3 py-2">
                      <div className="text-xs text-text-secondary">
                        <span className="font-medium text-text-primary">
                          {finding.assignee_name || "Unassigned"}
                        </span>
                        {" · "}
                        <span>{finding.due_date || "No target date"}</span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleSaveTriage}
                        disabled={savingTriage}
                      >
                        {savingTriage ? "Saving…" : "Save Triage"}
                      </Button>
                    </div>
                  </div>

                  {finding.references?.length > 0 && (
                    <>
                      <Separator />
                      <div>
                        <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
                          References
                        </h4>
                        <ul className="space-y-1.5">
                          {finding.references.map((ref: any) => (
                            <li key={ref.id} className="flex items-center gap-2 text-sm">
                              <span className="text-[10px] uppercase font-semibold text-text-tertiary px-1.5 py-0.5 rounded bg-surface-elevated">
                                {ref.reference_type}
                              </span>
                              {ref.url ? (
                                <a
                                  href={ref.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary hover:underline inline-flex items-center gap-1 text-xs"
                                >
                                  {ref.reference_value}
                                  <ExternalLink className="h-3 w-3" />
                                </a>
                              ) : (
                                <span className="text-xs text-text-secondary">
                                  {ref.reference_value}
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </>
                  )}

                  {finding.metadata_json &&
                    Object.keys(finding.metadata_json).length > 0 && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
                            Metadata
                          </h4>
                          <pre className="text-xs font-mono text-text-secondary bg-surface-elevated rounded-lg p-3 overflow-x-auto">
                            {JSON.stringify(finding.metadata_json, null, 2)}
                          </pre>
                        </div>
                      </>
                    )}

                  <Separator />
                  <div>
                    <h4 className="text-xs font-semibold text-text-tertiary uppercase tracking-wider mb-2">
                      Fingerprint
                    </h4>
                    <code className="text-xs font-mono text-text-tertiary">
                      {finding.canonical_fingerprint}
                    </code>
                  </div>
                </TabsContent>

                <TabsContent value="instances" className="p-5 mt-0 space-y-3">
                  {(finding.instances || []).length === 0 && (
                    <p className="text-sm text-text-tertiary text-center py-8">
                      No instances recorded
                    </p>
                  )}
                  {(finding.instances || []).map((inst: any) => (
                    <div
                      key={inst.id}
                      className="rounded-lg border border-border bg-surface-elevated p-3 space-y-2"
                    >
                      {inst.path && (
                        <div className="flex items-center gap-2 text-sm">
                          <FileText className="h-3.5 w-3.5 text-text-tertiary flex-shrink-0" />
                          <code className="text-xs font-mono text-text-primary">
                            {inst.path}
                            {inst.line_start ? `:${inst.line_start}` : ""}
                            {inst.line_end && inst.line_end !== inst.line_start
                              ? `-${inst.line_end}`
                              : ""}
                          </code>
                        </div>
                      )}
                      {inst.package_name && (
                        <div className="text-xs text-text-secondary">
                          Package:{" "}
                          <code className="font-mono">
                            {inst.package_name}@
                            {inst.installed_version || "?"}
                          </code>
                          {inst.fixed_version && (
                            <>
                              {" → "}
                              <code className="font-mono text-success">
                                {inst.fixed_version}
                              </code>
                            </>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-3 text-[11px] text-text-tertiary">
                        <span>
                          Scan:{" "}
                          <code className="font-mono">
                            {inst.scan_id.slice(0, 8)}
                          </code>
                        </span>
                        <span>{formatDate(inst.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </TabsContent>

                <TabsContent value="history" className="p-5 mt-0 space-y-0">
                  {(finding.events || []).length === 0 && (
                    <p className="text-sm text-text-tertiary text-center py-8">
                      No events recorded
                    </p>
                  )}
                  {(finding.events || []).map((evt: any, i: number) => (
                    <div key={evt.id} className="flex gap-3 relative">
                      <div className="flex flex-col items-center">
                        <div
                          className={cn(
                            "h-3 w-3 rounded-full border-2 mt-1 flex-shrink-0",
                            evt.event_type === "resolved"
                              ? "border-success bg-success/20"
                              : evt.event_type === "fixed"
                              ? "border-success bg-success/20"
                              : evt.event_type === "suppressed"
                              ? "border-text-tertiary bg-surface-elevated"
                              : evt.event_type === "accepted_risk"
                              ? "border-info bg-info/20"
                              : evt.event_type === "duplicate"
                              ? "border-border-strong bg-surface"
                              : evt.event_type === "reopened"
                              ? "border-warning bg-warning/20"
                              : "border-border bg-surface-elevated"
                          )}
                        />
                        {i < (finding.events || []).length - 1 && (
                          <div className="w-px flex-1 bg-border my-1" />
                        )}
                      </div>
                      <div className="pb-4 flex-1">
                        <span className="text-xs font-semibold text-text-primary capitalize">
                          {evt.event_type.replace(/_/g, " ")}
                        </span>
                        {evt.reason && (
                          <p className="text-xs text-text-secondary mt-0.5">
                            {evt.reason}
                          </p>
                        )}
                        <span className="text-[11px] text-text-tertiary mt-0.5 block">
                          {formatDate(evt.created_at)}
                        </span>
                      </div>
                    </div>
                  ))}
                </TabsContent>

                <TabsContent value="related" className="p-5 mt-0 space-y-2">
                  {related.length === 0 && (
                    <p className="text-sm text-text-tertiary text-center py-8">
                      No related findings found
                    </p>
                  )}
                  {related.map((f: any) => (
                    <button
                      key={f.id}
                      onClick={() =>
                        onSelectFinding && onSelectFinding(f.id)
                      }
                      className="w-full flex items-center gap-3 rounded-lg border border-border bg-surface-elevated p-3 text-left hover:bg-surface-hover transition-colors"
                    >
                      <SeverityBadge severity={f.severity} showDot={false} />
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-text-primary truncate block">
                          {f.title}
                        </span>
                        <span className="text-xs text-text-tertiary">
                          {f.status} · {f.primary_scanner}
                        </span>
                      </div>
                    </button>
                  ))}
                </TabsContent>
              </ScrollArea>
            </Tabs>

            {/* Footer Actions */}
            <div className="flex items-center gap-2 p-4 border-t border-border bg-surface">
              {finding.status === "open" && (
                <>
                  {actionForm.action === "" && (
                    <>
                      <Button
                        onClick={() =>
                          setActionForm({ ...actionForm, action: "resolve" })
                        }
                        className="flex-1 gap-1.5"
                      >
                        <CheckCircle className="h-4 w-4" /> Resolve
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() =>
                          setActionForm({ ...actionForm, action: "suppress" })
                        }
                        className="flex-1 gap-1.5"
                      >
                        <Ban className="h-4 w-4" /> Suppress
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() =>
                          setActionForm({
                            ...actionForm,
                            action: "accept_risk",
                          })
                        }
                        className="flex-1 gap-1.5"
                      >
                        <Shield className="h-4 w-4" /> Accept Risk
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() =>
                          setActionForm({
                            ...actionForm,
                            action: "mark_duplicate",
                          })
                        }
                        className="flex-1 gap-1.5"
                      >
                        <AlertTriangle className="h-4 w-4" /> Duplicate
                      </Button>
                    </>
                  )}
                  {actionForm.action && (
                    <div className="flex-1 space-y-2">
                      <h5 className="text-xs font-semibold text-text-primary">
                        {actionForm.action === "resolve"
                          ? "Resolve Finding"
                          : actionForm.action === "suppress"
                          ? "Suppress Finding"
                          : actionForm.action === "accept_risk"
                          ? "Accept Risk"
                          : "Mark Duplicate"}
                      </h5>
                      {actionForm.action === "resolve" && (
                        <Input
                          placeholder="Fixed version (optional)"
                          value={actionForm.fixedVersion}
                          onChange={(e) =>
                            setActionForm({
                              ...actionForm,
                              fixedVersion: e.target.value,
                            })
                          }
                          className="h-8 text-xs"
                        />
                      )}
                      <Input
                        required
                        placeholder="Reason"
                        value={actionForm.reason}
                        onChange={(e) =>
                          setActionForm({
                            ...actionForm,
                            reason: e.target.value,
                          })
                        }
                        className="h-8 text-xs"
                      />
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setActionForm({
                              action: "",
                              reason: "",
                              fixedVersion: "",
                            })
                          }
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          disabled={acting || !actionForm.reason}
                          onClick={() => handleAction(actionForm.action)}
                        >
                          {acting ? "Saving…" : "Confirm"}
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
              {(finding.status === "fixed" ||
                finding.status === "suppressed" ||
                finding.status === "accepted_risk" ||
                finding.status === "duplicate") && (
                <Button
                  variant="outline"
                  onClick={() => handleAction("reopen")}
                  disabled={acting}
                  className="flex-1 gap-1.5"
                >
                  <AlertTriangle className="h-4 w-4" />{" "}
                  {acting ? "Reopening…" : "Reopen"}
                </Button>
              )}
              {finding.status !== "open" &&
                finding.status !== "fixed" &&
                finding.status !== "suppressed" &&
                finding.status !== "accepted_risk" &&
                finding.status !== "duplicate" && (
                  <p className="text-xs text-text-tertiary flex-1 text-center py-1">
                    Finding is{" "}
                    <span className="capitalize">{finding.status}</span>
                  </p>
                )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
