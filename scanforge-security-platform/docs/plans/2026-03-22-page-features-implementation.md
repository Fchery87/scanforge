# ScanForge Page-by-Page Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all recommended features across 10 existing pages and build 6 new pages to complete ScanForge's security platform UI and supporting API endpoints.

**Architecture:** Frontend-first approach — each phase enhances pages from highest-impact to lowest. New API endpoints are added only when the frontend needs data the API doesn't yet provide. All frontend components are `"use client"` React 19 with CSS Modules. All API routes follow existing FastAPI patterns with Pydantic schemas. No new dependencies are added unless explicitly stated.

**Tech Stack:** Next.js 16, React 19, CSS Modules, Lucide React icons, FastAPI, SQLAlchemy 2.x, Pydantic 2.x, PostgreSQL

---

## Table of Contents

- [Phase 1: Critical Workflow Unlockers](#phase-1-critical-workflow-unlockers) (Tasks 1–8)
- [Phase 2: Data Wiring & Stats](#phase-2-data-wiring--stats) (Tasks 9–14)
- [Phase 3: Finding Detail & Triage](#phase-3-finding-detail--triage) (Tasks 15–20)
- [Phase 4: Scan Lifecycle](#phase-4-scan-lifecycle) (Tasks 21–27)
- [Phase 5: New Pages](#phase-5-new-pages) (Tasks 28–38)
- [Phase 6: Notifications & Navigation](#phase-6-notifications--navigation) (Tasks 39–44)
- [Phase 7: Enhancements & Polish](#phase-7-enhancements--polish) (Tasks 45–55)
- [Phase 8: Onboarding & Settings Completion](#phase-8-onboarding--settings-completion) (Tasks 56–60)

---

## Phase 1: Critical Workflow Unlockers

These tasks unblock the core scan → find → triage workflow that is currently non-functional in the UI.

---

### Task 1: Connect Repository Modal

The "Connect Repository" button on the Repositories page and Project Overview page is non-functional. Wire it to a working modal that calls the existing `POST /repositories` endpoint.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.module.css`
- Modify: `apps/web/lib/api.ts`

**Step 1: Add `create` method to the repositories API client**

In `apps/web/lib/api.ts`, the `repositories` object currently only has `list`. Add a `create` method:

```typescript
// Add inside the repositories object in lib/api.ts, after the list method
create: (orgId: string, projectId: string, data: {
  provider: string;
  owner_name: string;
  repo_name: string;
  full_name: string;
  default_branch?: string;
  clone_url?: string;
  html_url?: string;
}) =>
  request<any>(`/organizations/${orgId}/projects/${projectId}/repositories`, {
    method: "POST",
    body: JSON.stringify(data),
  }),
```

**Step 2: Add modal state and form to the repositories page**

In `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`, add:

```typescript
// Add state variables after existing state declarations
const [showModal, setShowModal] = useState(false);
const [form, setForm] = useState({
  provider: "github",
  owner_name: "",
  repo_name: "",
  full_name: "",
  default_branch: "main",
  clone_url: "",
  html_url: "",
});
const [error, setError] = useState("");

// Add submit handler
const handleConnect = async (e: React.FormEvent) => {
  e.preventDefault();
  setError("");
  try {
    const repo = await api.repositories.create(org_id, project_id, {
      ...form,
      full_name: form.full_name || `${form.owner_name}/${form.repo_name}`,
    });
    setRepos((prev: any[]) => [...prev, repo]);
    setShowModal(false);
    setForm({ provider: "github", owner_name: "", repo_name: "", full_name: "", default_branch: "main", clone_url: "", html_url: "" });
  } catch (err: any) {
    setError(err.message || "Failed to connect repository");
  }
};
```

**Step 3: Build the modal JSX**

Add the modal after the repository grid in the return JSX:

```tsx
{showModal && (
  <div className={s.modalOverlay} onClick={() => setShowModal(false)}>
    <div className={s.modal} onClick={(e) => e.stopPropagation()}>
      <h3>Connect Repository</h3>
      {error && <p className={s.error}>{error}</p>}
      <form onSubmit={handleConnect}>
        <label>Provider</label>
        <select value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })}>
          <option value="github">GitHub</option>
          <option value="gitlab">GitLab</option>
          <option value="bitbucket">Bitbucket</option>
          <option value="manual">Manual</option>
        </select>

        <label>Owner / Org Name</label>
        <input required value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} placeholder="e.g. my-org" />

        <label>Repository Name</label>
        <input required value={form.repo_name} onChange={(e) => setForm({ ...form, repo_name: e.target.value })} placeholder="e.g. my-repo" />

        <label>Default Branch</label>
        <input value={form.default_branch} onChange={(e) => setForm({ ...form, default_branch: e.target.value })} placeholder="main" />

        <label>Clone URL</label>
        <input value={form.clone_url} onChange={(e) => setForm({ ...form, clone_url: e.target.value })} placeholder="https://github.com/org/repo.git" />

        <label>HTML URL</label>
        <input value={form.html_url} onChange={(e) => setForm({ ...form, html_url: e.target.value })} placeholder="https://github.com/org/repo" />

        <div className={s.modalActions}>
          <button type="button" className={s.btnGhost} onClick={() => setShowModal(false)}>Cancel</button>
          <button type="submit" className={s.btnPrimary}>Connect</button>
        </div>
      </form>
    </div>
  </div>
)}
```

**Step 4: Wire the "Connect Repository" button to open the modal**

Replace the non-functional button with:
```tsx
<button className={s.btnPrimary} onClick={() => setShowModal(true)}>
  <Plus size={16} /> Connect Repository
</button>
```

**Step 5: Add modal CSS to the repositories page module**

Append to `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.module.css`:

```css
.modalOverlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: 28px; width: 100%; max-width: 480px;
}
.modal h3 { font-size: 18px; font-weight: 700; margin-bottom: 20px; }
.modal label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; margin-top: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
.modal input, .modal select {
  width: 100%; padding: 10px 12px; background: var(--bg-tertiary); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-primary); font-size: 14px;
}
.modal input:focus, .modal select:focus { border-color: var(--accent); outline: none; }
.modalActions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 24px; }
.btnPrimary {
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  background: var(--accent); color: #060a12; border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600; cursor: pointer; border: none;
}
.btnPrimary:hover { opacity: 0.9; }
.btnGhost {
  padding: 8px 16px; background: transparent; border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 13px; cursor: pointer;
}
.btnGhost:hover { border-color: var(--text-muted); }
.error { color: var(--red); background: var(--red-dim); padding: 8px 12px; border-radius: var(--radius-sm); font-size: 13px; margin-bottom: 12px; }
```

**Step 6: Verify**

Run: `cd apps/web && npm run build`
Expected: Build succeeds with no TypeScript errors.

**Step 7: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/
git commit -m "feat(web): wire Connect Repository modal to POST /repositories API"
```

---

### Task 2: Trigger Scan Modal

The "Trigger Scan" button on the Scans page is non-functional. Wire it to call `POST /scans`.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.module.css`

**Step 1: Add state for modal, repositories list, and form**

```typescript
const [showModal, setShowModal] = useState(false);
const [repos, setRepos] = useState<any[]>([]);
const [scanForm, setScanForm] = useState({
  repository_id: "",
  branch_name: "",
  scan_type: "full",
});
const [submitting, setSubmitting] = useState(false);
const [error, setError] = useState("");
```

**Step 2: Fetch repositories when modal opens**

```typescript
useEffect(() => {
  if (showModal && repos.length === 0) {
    api.repositories.list(org_id, project_id).then((res: any) => {
      setRepos(res.items || res);
      if (res.items?.[0]) setScanForm((f) => ({ ...f, repository_id: res.items[0].id }));
    });
  }
}, [showModal]);
```

**Step 3: Add submit handler**

```typescript
const handleTriggerScan = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!scanForm.repository_id) return;
  setSubmitting(true);
  setError("");
  try {
    const scan = await api.scans.create(org_id, project_id, {
      repository_id: scanForm.repository_id,
      trigger_type: "manual",
      branch_name: scanForm.branch_name || undefined,
    });
    setScans((prev: any[]) => [scan, ...prev]);
    setShowModal(false);
    setScanForm({ repository_id: "", branch_name: "", scan_type: "full" });
  } catch (err: any) {
    setError(err.message || "Failed to trigger scan");
  } finally {
    setSubmitting(false);
  }
};
```

**Step 4: Build the modal JSX**

```tsx
{showModal && (
  <div className={s.modalOverlay} onClick={() => setShowModal(false)}>
    <div className={s.modal} onClick={(e) => e.stopPropagation()}>
      <h3>Trigger Scan</h3>
      {error && <p className={s.error}>{error}</p>}
      <form onSubmit={handleTriggerScan}>
        <label>Repository</label>
        <select required value={scanForm.repository_id} onChange={(e) => setScanForm({ ...scanForm, repository_id: e.target.value })}>
          <option value="">Select repository…</option>
          {repos.map((r: any) => (
            <option key={r.id} value={r.id}>{r.full_name}</option>
          ))}
        </select>

        <label>Branch (optional)</label>
        <input value={scanForm.branch_name} onChange={(e) => setScanForm({ ...scanForm, branch_name: e.target.value })} placeholder="defaults to repo default branch" />

        <label>Scan Type</label>
        <select value={scanForm.scan_type} onChange={(e) => setScanForm({ ...scanForm, scan_type: e.target.value })}>
          <option value="full">Full Scan</option>
          <option value="dependencies">Dependencies Only</option>
          <option value="secrets">Secrets Only</option>
        </select>

        <div className={s.modalActions}>
          <button type="button" className={s.btnGhost} onClick={() => setShowModal(false)}>Cancel</button>
          <button type="submit" className={s.btnPrimary} disabled={submitting}>
            {submitting ? "Triggering…" : "Start Scan"}
          </button>
        </div>
      </form>
    </div>
  </div>
)}
```

**Step 5: Wire the button**

Replace the existing "Trigger Scan" button:
```tsx
<button className={s.btnPrimary} onClick={() => setShowModal(true)}>
  <Plus size={16} /> Trigger Scan
</button>
```

**Step 6: Add modal CSS** (same pattern as Task 1 — append to scans `page.module.css`)

Use identical `.modalOverlay`, `.modal`, `.modal label`, `.modal input`, `.modal select`, `.modalActions`, `.btnPrimary`, `.btnGhost`, `.error` classes as Task 1.

**Step 7: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/scans/
git commit -m "feat(web): wire Trigger Scan modal to POST /scans API"
```

---

### Task 3: Finding Detail Drawer

The most critical missing UI component. Users cannot see details of any finding. Build a slide-over drawer that opens when clicking a finding row.

**Files:**
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/FindingDrawer.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/FindingDrawer.module.css`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- Modify: `apps/web/lib/api.ts`

**Step 1: Add missing API methods to `lib/api.ts`**

```typescript
// Add to the findings object:
reopen: (orgId: string, projectId: string, findingId: string) =>
  request<any>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/reopen`, {
    method: "POST",
  }),
events: (orgId: string, projectId: string, findingId: string) =>
  request<any[]>(`/organizations/${orgId}/projects/${projectId}/findings/${findingId}/events`),
bulk: (orgId: string, projectId: string, data: { finding_ids: string[]; action: string; reason: string }) =>
  request<any>(`/organizations/${orgId}/projects/${projectId}/findings/bulk`, {
    method: "POST",
    body: JSON.stringify(data),
  }),
```

**Step 2: Create `FindingDrawer.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { X, ExternalLink, Clock, Shield, FileText, GitBranch, AlertTriangle, CheckCircle, Ban } from "lucide-react";
import { api } from "@/lib/api";
import s from "./FindingDrawer.module.css";

interface FindingDrawerProps {
  orgId: string;
  projectId: string;
  findingId: string;
  onClose: () => void;
  onUpdate: () => void;
}

export default function FindingDrawer({ orgId, projectId, findingId, onClose, onUpdate }: FindingDrawerProps) {
  const [finding, setFinding] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"details" | "instances" | "history">("details");
  const [actionForm, setActionForm] = useState({ action: "", reason: "", fixedVersion: "" });
  const [acting, setActing] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.findings.get(orgId, projectId, findingId).then((data) => {
      setFinding(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [findingId]);

  const handleAction = async (action: string) => {
    if (!actionForm.reason && action !== "reopen") return;
    setActing(true);
    try {
      if (action === "suppress") {
        await api.findings.suppress(orgId, projectId, findingId, actionForm.reason);
      } else if (action === "resolve") {
        await api.findings.resolve(orgId, projectId, findingId, actionForm.fixedVersion);
      } else if (action === "reopen") {
        await api.findings.reopen(orgId, projectId, findingId);
      }
      onUpdate();
      // Refresh finding data
      const updated = await api.findings.get(orgId, projectId, findingId);
      setFinding(updated);
      setActionForm({ action: "", reason: "", fixedVersion: "" });
    } catch (err) {
      console.error(err);
    } finally {
      setActing(false);
    }
  };

  const severityColor = (sev: string) => {
    const map: Record<string, string> = { critical: "var(--red)", high: "#fb923c", medium: "var(--amber)", low: "var(--green)", info: "var(--accent)" };
    return map[sev] || "var(--text-muted)";
  };

  const formatDate = (d: string) => new Date(d).toLocaleString();

  const daysSince = (d: string) => {
    const days = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
    if (days === 0) return "today";
    if (days === 1) return "1 day ago";
    return `${days} days ago`;
  };

  if (loading) return (
    <div className={s.overlay} onClick={onClose}>
      <div className={s.drawer} onClick={(e) => e.stopPropagation()}>
        <div className={s.loading}>Loading…</div>
      </div>
    </div>
  );

  if (!finding) return null;

  return (
    <div className={s.overlay} onClick={onClose}>
      <div className={s.drawer} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={s.header}>
          <div className={s.headerTop}>
            <span className={s.severityBadge} style={{ borderColor: severityColor(finding.severity), color: severityColor(finding.severity) }}>
              {finding.severity}
            </span>
            <span className={s.statusBadge} data-status={finding.status}>{finding.status}</span>
            <button className={s.closeBtn} onClick={onClose} aria-label="Close"><X size={18} /></button>
          </div>
          <h2 className={s.title}>{finding.title}</h2>
          <div className={s.meta}>
            <span><Clock size={12} /> First seen {daysSince(finding.first_seen_at)}</span>
            <span><Shield size={12} /> {finding.primary_scanner}</span>
            <span>{finding.category}</span>
          </div>
        </div>

        {/* Tabs */}
        <div className={s.tabs}>
          <button className={tab === "details" ? s.tabActive : s.tab} onClick={() => setTab("details")}>Details</button>
          <button className={tab === "instances" ? s.tabActive : s.tab} onClick={() => setTab("instances")}>
            Instances ({finding.instances?.length || 0})
          </button>
          <button className={tab === "history" ? s.tabActive : s.tab} onClick={() => setTab("history")}>
            History ({finding.events?.length || 0})
          </button>
        </div>

        {/* Tab Content */}
        <div className={s.body}>
          {tab === "details" && (
            <>
              {finding.description && (
                <div className={s.section}>
                  <h4 className={s.sectionTitle}>Description</h4>
                  <p className={s.description}>{finding.description}</p>
                </div>
              )}

              {finding.fixed_version && (
                <div className={s.section}>
                  <h4 className={s.sectionTitle}>Remediation</h4>
                  <p className={s.remediation}>Upgrade to version <code>{finding.fixed_version}</code></p>
                </div>
              )}

              {finding.references?.length > 0 && (
                <div className={s.section}>
                  <h4 className={s.sectionTitle}>References</h4>
                  <ul className={s.refList}>
                    {finding.references.map((ref: any) => (
                      <li key={ref.id}>
                        <span className={s.refType}>{ref.reference_type}</span>
                        {ref.url ? (
                          <a href={ref.url} target="_blank" rel="noopener noreferrer" className={s.refLink}>
                            {ref.reference_value} <ExternalLink size={11} />
                          </a>
                        ) : (
                          <span className={s.refValue}>{ref.reference_value}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {finding.metadata_json && Object.keys(finding.metadata_json).length > 0 && (
                <div className={s.section}>
                  <h4 className={s.sectionTitle}>Metadata</h4>
                  <pre className={s.json}>{JSON.stringify(finding.metadata_json, null, 2)}</pre>
                </div>
              )}

              <div className={s.section}>
                <h4 className={s.sectionTitle}>Fingerprint</h4>
                <code className={s.fingerprint}>{finding.canonical_fingerprint}</code>
              </div>
            </>
          )}

          {tab === "instances" && (
            <div className={s.instanceList}>
              {(finding.instances || []).length === 0 && <p className={s.empty}>No instances recorded</p>}
              {(finding.instances || []).map((inst: any) => (
                <div key={inst.id} className={s.instanceCard}>
                  {inst.path && (
                    <div className={s.instancePath}>
                      <FileText size={13} />
                      <code>{inst.path}{inst.line_start ? `:${inst.line_start}` : ""}{inst.line_end && inst.line_end !== inst.line_start ? `-${inst.line_end}` : ""}</code>
                    </div>
                  )}
                  {inst.package_name && (
                    <div className={s.instancePkg}>
                      Package: <code>{inst.package_name}@{inst.installed_version || "?"}</code>
                      {inst.fixed_version && <> → <code>{inst.fixed_version}</code></>}
                    </div>
                  )}
                  <div className={s.instanceMeta}>
                    <span>Scan: <code>{inst.scan_id.slice(0, 8)}</code></span>
                    <span>{formatDate(inst.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "history" && (
            <div className={s.timeline}>
              {(finding.events || []).length === 0 && <p className={s.empty}>No events recorded</p>}
              {(finding.events || []).map((evt: any) => (
                <div key={evt.id} className={s.timelineItem}>
                  <div className={s.timelineDot} data-type={evt.event_type} />
                  <div className={s.timelineContent}>
                    <span className={s.eventType}>{evt.event_type.replace(/_/g, " ")}</span>
                    {evt.reason && <p className={s.eventReason}>{evt.reason}</p>}
                    <span className={s.eventTime}>{formatDate(evt.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className={s.actions}>
          {finding.status === "open" && (
            <>
              {actionForm.action === "" && (
                <div className={s.actionButtons}>
                  <button className={s.btnResolve} onClick={() => setActionForm({ ...actionForm, action: "resolve" })}>
                    <CheckCircle size={14} /> Resolve
                  </button>
                  <button className={s.btnSuppress} onClick={() => setActionForm({ ...actionForm, action: "suppress" })}>
                    <Ban size={14} /> Suppress
                  </button>
                </div>
              )}
              {actionForm.action && (
                <div className={s.actionForm}>
                  <h5>{actionForm.action === "resolve" ? "Resolve Finding" : "Suppress Finding"}</h5>
                  {actionForm.action === "resolve" && (
                    <input placeholder="Fixed version (optional)" value={actionForm.fixedVersion}
                      onChange={(e) => setActionForm({ ...actionForm, fixedVersion: e.target.value })} />
                  )}
                  <input required placeholder="Reason" value={actionForm.reason}
                    onChange={(e) => setActionForm({ ...actionForm, reason: e.target.value })} />
                  <div className={s.actionFormButtons}>
                    <button className={s.btnGhost} onClick={() => setActionForm({ action: "", reason: "", fixedVersion: "" })}>Cancel</button>
                    <button className={s.btnPrimary} disabled={acting || !actionForm.reason}
                      onClick={() => handleAction(actionForm.action)}>
                      {acting ? "Saving…" : "Confirm"}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
          {(finding.status === "fixed" || finding.status === "suppressed") && (
            <button className={s.btnReopen} onClick={() => handleAction("reopen")} disabled={acting}>
              <AlertTriangle size={14} /> {acting ? "Reopening…" : "Reopen"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Create `FindingDrawer.module.css`**

```css
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5); backdrop-filter: blur(2px);
  z-index: 100; display: flex; justify-content: flex-end;
}
.drawer {
  width: 560px; max-width: 90vw; height: 100vh; background: var(--bg-secondary);
  border-left: 1px solid var(--border); display: flex; flex-direction: column;
  overflow: hidden; animation: slideIn 0.2s ease-out;
}
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
.loading { padding: 40px; text-align: center; color: var(--text-muted); }
.header { padding: 20px 24px 16px; border-bottom: 1px solid var(--border); }
.headerTop { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.severityBadge {
  font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 2px 8px;
  border: 1px solid; border-radius: 4px; letter-spacing: 0.05em;
}
.statusBadge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: var(--bg-tertiary); color: var(--text-secondary); text-transform: capitalize;
}
.statusBadge[data-status="open"] { background: var(--red-dim); color: var(--red); }
.statusBadge[data-status="fixed"] { background: var(--green-dim); color: var(--green); }
.statusBadge[data-status="suppressed"] { background: var(--purple-dim); color: var(--purple); }
.closeBtn {
  margin-left: auto; background: none; border: none; color: var(--text-muted);
  cursor: pointer; padding: 4px; border-radius: 4px;
}
.closeBtn:hover { color: var(--text-primary); background: var(--bg-tertiary); }
.title { font-size: 16px; font-weight: 700; line-height: 1.4; margin-bottom: 8px; }
.meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-muted); }
.meta span { display: flex; align-items: center; gap: 4px; }
.tabs {
  display: flex; border-bottom: 1px solid var(--border); padding: 0 24px;
}
.tab, .tabActive {
  padding: 10px 16px; font-size: 13px; font-weight: 500; background: none; border: none;
  border-bottom: 2px solid transparent; color: var(--text-muted); cursor: pointer;
}
.tabActive { color: var(--accent); border-bottom-color: var(--accent); }
.tab:hover { color: var(--text-secondary); }
.body { flex: 1; overflow-y: auto; padding: 20px 24px; }
.section { margin-bottom: 20px; }
.sectionTitle {
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-muted); margin-bottom: 8px;
}
.description { font-size: 13px; line-height: 1.6; color: var(--text-secondary); }
.remediation { font-size: 13px; color: var(--text-secondary); }
.remediation code { background: var(--green-dim); color: var(--green); padding: 2px 6px; border-radius: 3px; font-size: 12px; }
.refList { list-style: none; padding: 0; }
.refList li { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px solid var(--border-subtle); }
.refType { font-size: 10px; font-weight: 600; text-transform: uppercase; color: var(--text-muted); min-width: 40px; }
.refLink { color: var(--accent); display: flex; align-items: center; gap: 4px; }
.refLink:hover { text-decoration: underline; }
.refValue { color: var(--text-secondary); }
.json {
  font-family: "DM Mono", monospace; font-size: 11px; color: var(--text-secondary);
  background: var(--bg-primary); padding: 12px; border-radius: var(--radius-sm);
  overflow-x: auto; max-height: 200px;
}
.fingerprint {
  font-family: "DM Mono", monospace; font-size: 11px; color: var(--text-muted);
  word-break: break-all;
}
.empty { color: var(--text-muted); font-size: 13px; text-align: center; padding: 24px 0; }
.instanceList { display: flex; flex-direction: column; gap: 8px; }
.instanceCard {
  padding: 12px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.instancePath { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.instancePath code { font-size: 12px; color: var(--accent); }
.instancePkg { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.instancePkg code { font-size: 11px; background: var(--bg-tertiary); padding: 1px 4px; border-radius: 2px; }
.instanceMeta { display: flex; gap: 16px; font-size: 11px; color: var(--text-muted); }
.instanceMeta code { font-family: "DM Mono", monospace; }
.timeline { display: flex; flex-direction: column; gap: 0; }
.timelineItem { display: flex; gap: 12px; padding: 10px 0; border-left: 2px solid var(--border); margin-left: 6px; padding-left: 16px; position: relative; }
.timelineDot {
  position: absolute; left: -5px; top: 14px; width: 8px; height: 8px;
  border-radius: 50%; background: var(--text-muted);
}
.timelineDot[data-type="opened"] { background: var(--red); }
.timelineDot[data-type="reopened"] { background: var(--amber); }
.timelineDot[data-type="fixed"] { background: var(--green); }
.timelineDot[data-type="suppressed"] { background: var(--purple); }
.timelineContent { flex: 1; }
.eventType { font-size: 13px; font-weight: 600; text-transform: capitalize; }
.eventReason { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.eventTime { font-size: 11px; color: var(--text-muted); font-family: "DM Mono", monospace; }
.actions { padding: 16px 24px; border-top: 1px solid var(--border); }
.actionButtons { display: flex; gap: 8px; }
.btnResolve {
  display: flex; align-items: center; gap: 6px; padding: 8px 16px;
  background: var(--green-dim); color: var(--green); border: 1px solid rgba(74,222,128,0.3);
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer;
}
.btnResolve:hover { background: rgba(74,222,128,0.2); }
.btnSuppress {
  display: flex; align-items: center; gap: 6px; padding: 8px 16px;
  background: var(--purple-dim); color: var(--purple); border: 1px solid rgba(167,139,250,0.3);
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer;
}
.btnSuppress:hover { background: rgba(167,139,250,0.2); }
.btnReopen {
  display: flex; align-items: center; gap: 6px; padding: 8px 16px;
  background: var(--amber-dim); color: var(--amber); border: 1px solid rgba(251,191,36,0.3);
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer;
}
.actionForm { display: flex; flex-direction: column; gap: 8px; }
.actionForm h5 { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.actionForm input {
  width: 100%; padding: 8px 12px; background: var(--bg-tertiary); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-primary); font-size: 13px;
}
.actionForm input:focus { border-color: var(--accent); outline: none; }
.actionFormButtons { display: flex; gap: 8px; justify-content: flex-end; }
.btnPrimary {
  padding: 8px 16px; background: var(--accent); color: #060a12;
  border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; border: none;
}
.btnPrimary:disabled { opacity: 0.5; cursor: not-allowed; }
.btnGhost {
  padding: 8px 16px; background: transparent; border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 13px; cursor: pointer;
}
```

**Step 4: Wire the drawer into the findings page**

In `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`:

Add import at top:
```typescript
import FindingDrawer from "./FindingDrawer";
```

Add state:
```typescript
const [selectedFinding, setSelectedFinding] = useState<string | null>(null);
```

Make each finding row clickable (on the title cell):
```tsx
<td className={s.titleCell} style={{ cursor: "pointer" }}
  onClick={() => setSelectedFinding(f.id)}>
  {f.title}
</td>
```

Add drawer at end of component return, before the closing fragment:
```tsx
{selectedFinding && (
  <FindingDrawer
    orgId={org_id}
    projectId={project_id}
    findingId={selectedFinding}
    onClose={() => setSelectedFinding(null)}
    onUpdate={() => {
      api.findings.list(org_id, project_id, Object.fromEntries(searchParams.entries())).then((res: any) => setFindings(res));
    }}
  />
)}
```

**Step 5: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/ apps/web/lib/api.ts
git commit -m "feat(web): add Finding Detail drawer with instances, history, and actions"
```

---

### Task 4: Bulk Actions — Resolve and Accept Risk

The findings page only supports bulk suppress. Add bulk resolve and bulk accept risk.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`

**Step 1: Add bulk resolve handler**

```typescript
const handleBulkResolve = async () => {
  if (selected.length === 0) return;
  const reason = prompt("Reason for resolving:");
  if (!reason) return;
  try {
    await api.findings.bulk(org_id, project_id, { finding_ids: selected, action: "resolve", reason });
    setSelected([]);
    const res = await api.findings.list(org_id, project_id, params);
    setFindings(res);
  } catch (err) { console.error(err); }
};
```

**Step 2: Add buttons in the bulk actions bar**

Next to the existing Suppress button, add:
```tsx
<button className={s.btnPrimary} onClick={handleBulkResolve} style={{ background: "var(--green-dim)", color: "var(--green)" }}>
  Resolve ({selected.length})
</button>
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/page.tsx
git commit -m "feat(web): add bulk resolve action to findings page"
```

---

### Task 5: Repository and Scanner Filters on Findings Page

The API supports `repositoryId` and `scanner` query params but the UI doesn't expose them.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`

**Step 1: Fetch repositories on mount for the filter dropdown**

```typescript
const [repos, setRepos] = useState<any[]>([]);

useEffect(() => {
  api.repositories.list(org_id, project_id).then((res: any) => {
    setRepos(res.items || res);
  });
}, [org_id, project_id]);
```

**Step 2: Add filter dropdowns after the existing status filter**

```tsx
<select className={s.filterSelect} value={params.repositoryId || ""}
  onChange={(e) => updateParams({ repositoryId: e.target.value || undefined })}>
  <option value="">All Repositories</option>
  {repos.map((r: any) => (
    <option key={r.id} value={r.id}>{r.full_name}</option>
  ))}
</select>

<select className={s.filterSelect} value={params.scanner || ""}
  onChange={(e) => updateParams({ scanner: e.target.value || undefined })}>
  <option value="">All Scanners</option>
  <option value="trivy">Trivy</option>
  <option value="gitleaks">Gitleaks</option>
  <option value="osv">OSV-Scanner</option>
</select>
```

Where `updateParams` is a helper that updates URL search params:
```typescript
const updateParams = (updates: Record<string, string | undefined>) => {
  const newParams = new URLSearchParams(searchParams.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value) newParams.set(key, value);
    else newParams.delete(key);
  }
  newParams.set("skip", "0");
  router.replace(`?${newParams.toString()}`);
};
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/page.tsx
git commit -m "feat(web): add repository and scanner filter dropdowns to findings page"
```

---

### Task 6: Cancel Scan Button

The API has `POST /scans/{scan_id}/cancel` but no UI. Add a cancel button on queued/running scans.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx`
- Modify: `apps/web/lib/api.ts`

**Step 1: Add cancel method to API client**

```typescript
// Add inside scans object in lib/api.ts
cancel: (orgId: string, projectId: string, scanId: string, reason?: string) =>
  request<any>(`/organizations/${orgId}/projects/${projectId}/scans/${scanId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  }),
```

**Step 2: Add cancel handler on the scans page**

```typescript
const handleCancel = async (scanId: string) => {
  try {
    const updated = await api.scans.cancel(org_id, project_id, scanId, "Canceled from UI");
    setScans((prev: any[]) => prev.map((s: any) => s.id === scanId ? updated : s));
  } catch (err) { console.error(err); }
};
```

**Step 3: Add cancel button in each scan row for queued/running scans**

```tsx
{(scan.status === "queued" || scan.status === "running") && (
  <button className={s.cancelBtn} onClick={() => handleCancel(scan.id)} title="Cancel scan">
    <XCircle size={14} />
  </button>
)}
```

**Step 4: Add CSS**

```css
.cancelBtn {
  background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px;
}
.cancelBtn:hover { color: var(--red); }
```

**Step 5: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/scans/
git commit -m "feat(web): add cancel button for queued/running scans"
```

---

### Task 7: Member Management on Org Settings

The settings page has a non-functional "Invite Member" button. Wire up invite, role editing, and member removal.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.module.css`
- Modify: `apps/web/lib/api.ts`

**Step 1: Add membership API methods to `lib/api.ts`**

```typescript
// Add new top-level section in the api object
members: {
  list: (orgId: string, skip = 0, limit = 50) =>
    request<any>(`/organizations/${orgId}/members?skip=${skip}&limit=${limit}`),
  invite: (orgId: string, data: { email: string; role: string }) =>
    request<any>(`/organizations/${orgId}/members`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateRole: (orgId: string, userId: string, role: string) =>
    request<any>(`/organizations/${orgId}/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  remove: (orgId: string, userId: string) =>
    request<any>(`/organizations/${orgId}/members/${userId}`, {
      method: "DELETE",
    }),
},
```

**Step 2: Add invite modal state to settings page**

```typescript
const [showInvite, setShowInvite] = useState(false);
const [inviteForm, setInviteForm] = useState({ email: "", role: "developer" });
const [inviteError, setInviteError] = useState("");
const [members, setMembers] = useState<any[]>([]);

// Fetch members
useEffect(() => {
  if (org) {
    api.members.list(org_id).then((res: any) => setMembers(res.items || []));
  }
}, [org]);

const handleInvite = async (e: React.FormEvent) => {
  e.preventDefault();
  setInviteError("");
  try {
    await api.members.invite(org_id, inviteForm);
    setShowInvite(false);
    setInviteForm({ email: "", role: "developer" });
    const res = await api.members.list(org_id);
    setMembers(res.items || []);
  } catch (err: any) {
    setInviteError(err.message || "Failed to invite member");
  }
};

const handleRoleChange = async (userId: string, newRole: string) => {
  try {
    await api.members.updateRole(org_id, userId, newRole);
    setMembers((prev) => prev.map((m) => m.user_id === userId ? { ...m, role: newRole } : m));
  } catch (err) { console.error(err); }
};

const handleRemoveMember = async (userId: string) => {
  if (!confirm("Remove this member? They will lose access to all projects.")) return;
  try {
    await api.members.remove(org_id, userId);
    setMembers((prev) => prev.filter((m) => m.user_id !== userId));
  } catch (err) { console.error(err); }
};
```

**Step 3: Replace the static members list with functional components**

Replace the members section in the settings page with:
```tsx
<div className={s.card}>
  <div className={s.cardHeader}>
    <h3>Members</h3>
    <button className={s.btnPrimary} onClick={() => setShowInvite(true)}>Invite Member</button>
  </div>
  <div className={s.memberList}>
    {members.map((m: any) => (
      <div key={m.id} className={s.memberRow}>
        <div className={s.memberInfo}>
          <div className={s.memberAvatar}>{(m.user_name || m.user_email || "?")[0].toUpperCase()}</div>
          <div>
            <span className={s.memberName}>{m.user_name || m.user_email}</span>
            {m.user_email && <span className={s.memberEmail}>{m.user_email}</span>}
          </div>
        </div>
        <div className={s.memberActions}>
          <select value={m.role} onChange={(e) => handleRoleChange(m.user_id, e.target.value)} className={s.roleSelect}>
            <option value="owner">Owner</option>
            <option value="admin">Admin</option>
            <option value="security_reviewer">Security Reviewer</option>
            <option value="developer">Developer</option>
            <option value="viewer">Viewer</option>
          </select>
          <button className={s.removeBtn} onClick={() => handleRemoveMember(m.user_id)} title="Remove member">
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    ))}
  </div>
</div>

{showInvite && (
  <div className={s.modalOverlay} onClick={() => setShowInvite(false)}>
    <div className={s.modal} onClick={(e) => e.stopPropagation()}>
      <h3>Invite Member</h3>
      {inviteError && <p className={s.error}>{inviteError}</p>}
      <form onSubmit={handleInvite}>
        <label>Email</label>
        <input type="email" required value={inviteForm.email}
          onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
          placeholder="user@example.com" />
        <label>Role</label>
        <select value={inviteForm.role}
          onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}>
          <option value="admin">Admin</option>
          <option value="security_reviewer">Security Reviewer</option>
          <option value="developer">Developer</option>
          <option value="viewer">Viewer</option>
        </select>
        <div className={s.modalActions}>
          <button type="button" className={s.btnGhost} onClick={() => setShowInvite(false)}>Cancel</button>
          <button type="submit" className={s.btnPrimary}>Send Invite</button>
        </div>
      </form>
    </div>
  </div>
)}
```

**Step 4: Add CSS for member management**

Append to settings `page.module.css`:
```css
.cardHeader { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.memberList { display: flex; flex-direction: column; }
.memberRow {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 1px solid var(--border-subtle);
}
.memberRow:last-child { border-bottom: none; }
.memberInfo { display: flex; align-items: center; gap: 10px; }
.memberAvatar {
  width: 32px; height: 32px; border-radius: 50%; background: var(--accent-dim);
  color: var(--accent); display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
}
.memberName { font-size: 14px; font-weight: 500; display: block; }
.memberEmail { font-size: 12px; color: var(--text-muted); display: block; }
.memberActions { display: flex; align-items: center; gap: 8px; }
.roleSelect {
  padding: 4px 8px; background: var(--bg-tertiary); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-primary); font-size: 12px;
}
.removeBtn {
  background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px;
}
.removeBtn:hover { color: var(--red); }
```

Plus the standard modal/button CSS classes if not already present.

**Step 5: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/settings/
git commit -m "feat(web): wire member invite, role editing, and removal on org settings"
```

---

### Task 8: Wire "Connect Repository" on Project Overview Page

The Project Overview page also has a "Connect Repository" button. Wire it to navigate to the repositories page with a query param to auto-open the modal.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`

**Step 1: Change the button on project overview to navigate**

```tsx
<Link href={`/dashboard/${org_id}/projects/${project_id}/repositories?connect=true`} className={s.btnPrimary}>
  <Database size={16} /> Connect Repository
</Link>
```

**Step 2: In the repositories page, auto-open modal if `connect=true` param exists**

```typescript
const searchParams = useSearchParams();
useEffect(() => {
  if (searchParams.get("connect") === "true") {
    setShowModal(true);
  }
}, [searchParams]);
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/page.tsx
git commit -m "feat(web): wire Connect Repository button on project overview to repos page modal"
```

---

## Phase 2: Data Wiring & Stats

Wire up placeholder stats and add the scorecard visualization.

---

### Task 9: New API Endpoint — Organization Stats

The org detail page shows "Open Findings: —" and "Scans Today: —" because no aggregate endpoint exists. Create one.

**Files:**
- Create: `apps/api/app/api/v1/routes/org_stats.py`
- Modify: `apps/api/app/api/v1/router.py`

**Step 1: Create the stats route**

```python
# apps/api/app/api/v1/routes/org_stats.py
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.finding import Finding
from app.db.models.project import Project
from app.db.models.scan import Scan
from app.db.session import get_db

router = APIRouter()


class OrgStatsResponse(BaseModel):
    project_count: int = 0
    open_findings: int = 0
    critical_findings: int = 0
    scans_today: int = 0
    scans_this_week: int = 0


@router.get("/organizations/{org_id}/stats", response_model=OrgStatsResponse)
async def get_org_stats(org_id: UUID, db: AsyncSession = Depends(get_db)):
    # Project count
    project_count = (
        await db.execute(
            select(func.count()).select_from(Project).where(Project.organization_id == org_id, Project.is_active == True)
        )
    ).scalar_one()

    # Project IDs for this org
    project_ids_result = await db.execute(
        select(Project.id).where(Project.organization_id == org_id)
    )
    project_ids = [r[0] for r in project_ids_result.all()]

    if not project_ids:
        return OrgStatsResponse(project_count=project_count)

    # Open findings across all projects
    open_findings = (
        await db.execute(
            select(func.count()).select_from(Finding).where(
                Finding.project_id.in_(project_ids), Finding.status == "open"
            )
        )
    ).scalar_one()

    # Critical findings
    critical_findings = (
        await db.execute(
            select(func.count()).select_from(Finding).where(
                Finding.project_id.in_(project_ids),
                Finding.status == "open",
                Finding.severity == "critical",
            )
        )
    ).scalar_one()

    # Scans today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    scans_today = (
        await db.execute(
            select(func.count()).select_from(Scan).where(
                Scan.project_id.in_(project_ids), Scan.created_at >= today_start
            )
        )
    ).scalar_one()

    # Scans this week
    week_start = today_start - timedelta(days=today_start.weekday())
    scans_this_week = (
        await db.execute(
            select(func.count()).select_from(Scan).where(
                Scan.project_id.in_(project_ids), Scan.created_at >= week_start
            )
        )
    ).scalar_one()

    return OrgStatsResponse(
        project_count=project_count,
        open_findings=open_findings,
        critical_findings=critical_findings,
        scans_today=scans_today,
        scans_this_week=scans_this_week,
    )
```

**Step 2: Register in router.py**

```python
from app.api.v1.routes import org_stats
api_router.include_router(org_stats.router, tags=["organizations"])
```

**Step 3: Commit**

```bash
git add apps/api/app/api/v1/routes/org_stats.py apps/api/app/api/v1/router.py
git commit -m "feat(api): add GET /organizations/{org_id}/stats endpoint for aggregate stats"
```

---

### Task 10: Wire Org Stats to Frontend

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`

**Step 1: Add API method**

```typescript
// Add to organizations object in lib/api.ts
stats: (orgId: string) =>
  request<any>(`/organizations/${orgId}/stats`),
```

**Step 2: Fetch and display stats on the org page**

Replace the hardcoded "—" values. Add stats state:
```typescript
const [stats, setStats] = useState<any>(null);
```

In the `useEffect` fetch, add:
```typescript
api.organizations.stats(org_id).then(setStats).catch(() => {});
```

Replace the stat card values:
- "Open Findings" card: `{stats?.open_findings ?? "—"}`
- "Scans Today" card: `{stats?.scans_today ?? "—"}`

**Step 3: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/page.tsx
git commit -m "feat(web): wire org-level stats (open findings, scans today) to API"
```

---

### Task 11: New API Endpoint — Project Stats with Enriched List

The project cards on the org page show "— repos" and "— findings". Enrich the projects list endpoint response.

**Files:**
- Modify: `apps/api/app/api/v1/routes/projects.py`

**Step 1: Add stats to the list response**

In the `list_projects` endpoint, after fetching projects, add a stats subquery for each project. The simplest approach is to add `repo_count` and `open_findings_count` to the list response using a subquery join:

```python
# In the list_projects handler, after fetching projects, enrich with counts:
enriched = []
for project in projects:
    repo_count = (await db.execute(
        select(func.count()).select_from(Repository).where(Repository.project_id == project.id)
    )).scalar_one()
    open_count = (await db.execute(
        select(func.count()).select_from(Finding).where(Finding.project_id == project.id, Finding.status == "open")
    )).scalar_one()
    proj_dict = {**ProjectResponse.model_validate(project).model_dump(), "repo_count": repo_count, "open_findings_count": open_count}
    enriched.append(proj_dict)
```

Add imports at top of `projects.py`:
```python
from app.db.models.repository import Repository
from app.db.models.finding import Finding
```

Return `enriched` in the paginated response instead of raw projects.

**Step 2: Commit**

```bash
git add apps/api/app/api/v1/routes/projects.py
git commit -m "feat(api): enrich project list response with repo_count and open_findings_count"
```

---

### Task 12: Wire Project Stats to Org Page Cards

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`

**Step 1: Replace placeholder badges on project cards**

Replace `"— repos"` with `{proj.repo_count ?? 0} repos` and `"— findings"` with `{proj.open_findings_count ?? 0} findings`.

Color the findings badge:
```tsx
<span className={proj.open_findings_count > 0 ? s.projectBadgeWarn : s.projectBadge}>
  {proj.open_findings_count ?? 0} findings
</span>
```

**Step 2: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/page.tsx
git commit -m "feat(web): display real repo and finding counts on project cards"
```

---

### Task 13: New API Endpoint — Project Scorecard

Surface the scoring logic from `apps/worker/app/services/scorecard.py` as an API endpoint.

**Files:**
- Create: `apps/api/app/api/v1/routes/scorecard.py`
- Modify: `apps/api/app/api/v1/router.py`

**Step 1: Create the scorecard route**

```python
# apps/api/app/api/v1/routes/scorecard.py
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.finding import Finding
from app.db.models.scan import Scan
from app.db.session import get_db

router = APIRouter()


class ScorecardResponse(BaseModel):
    project_id: str
    overall_score: float = 100.0
    security_score: float = 100.0
    secrets_score: float = 100.0
    dependency_score: float = 100.0
    grade: str = "A+"
    open_critical: int = 0
    open_high: int = 0
    open_medium: int = 0
    open_low: int = 0
    open_total: int = 0
    fixed_30d: int = 0
    new_this_week: int = 0
    scan_count: int = 0
    last_scan_at: str | None = None


def _grade(score: float) -> str:
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


@router.get(
    "/organizations/{org_id}/projects/{project_id}/scorecard",
    response_model=ScorecardResponse,
)
async def get_project_scorecard(
    org_id: UUID, project_id: UUID, db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)

    # Open findings by severity
    sev_counts = {}
    for sev in ("critical", "high", "medium", "low"):
        count = (await db.execute(
            select(func.count()).select_from(Finding).where(
                Finding.project_id == project_id, Finding.status == "open", Finding.severity == sev
            )
        )).scalar_one()
        sev_counts[sev] = count

    open_total = sum(sev_counts.values())

    # Security score
    penalty = sev_counts["critical"] * 25 + sev_counts["high"] * 10 + sev_counts["medium"] * 3 + sev_counts["low"] * 0.5
    security_score = round(max(0, 100 - penalty), 1)

    # Secrets score
    open_secrets = (await db.execute(
        select(func.count()).select_from(Finding).where(
            Finding.project_id == project_id, Finding.status == "open", Finding.category == "secret"
        )
    )).scalar_one()
    secrets_score = round(max(0, 100 - min(open_secrets * 20, 100)), 1)

    # Dependency score (simplified — count open dependency findings)
    open_deps = (await db.execute(
        select(func.count()).select_from(Finding).where(
            Finding.project_id == project_id, Finding.status == "open",
            Finding.category.in_(["vulnerability", "dependency_outdated"])
        )
    )).scalar_one()
    dep_penalty = min(open_deps * 5, 100)
    dependency_score = round(max(0, 100 - dep_penalty), 1)

    # Overall
    overall = round(security_score * 0.5 + secrets_score * 0.3 + dependency_score * 0.2, 1)

    # Fixed in last 30 days
    thirty_days_ago = now - timedelta(days=30)
    fixed_30d = (await db.execute(
        select(func.count()).select_from(Finding).where(
            Finding.project_id == project_id, Finding.status == "fixed",
            Finding.updated_at >= thirty_days_ago
        )
    )).scalar_one()

    # New this week
    week_ago = now - timedelta(days=7)
    new_this_week = (await db.execute(
        select(func.count()).select_from(Finding).where(
            Finding.project_id == project_id, Finding.first_seen_at >= week_ago
        )
    )).scalar_one()

    # Scan info
    scan_count = (await db.execute(
        select(func.count()).select_from(Scan).where(Scan.project_id == project_id)
    )).scalar_one()
    last_scan = (await db.execute(
        select(Scan.created_at).where(Scan.project_id == project_id).order_by(Scan.created_at.desc()).limit(1)
    )).scalar_one_or_none()

    return ScorecardResponse(
        project_id=str(project_id),
        overall_score=overall,
        security_score=security_score,
        secrets_score=secrets_score,
        dependency_score=dependency_score,
        grade=_grade(overall),
        open_critical=sev_counts["critical"],
        open_high=sev_counts["high"],
        open_medium=sev_counts["medium"],
        open_low=sev_counts["low"],
        open_total=open_total,
        fixed_30d=fixed_30d,
        new_this_week=new_this_week,
        scan_count=scan_count,
        last_scan_at=last_scan.isoformat() if last_scan else None,
    )
```

**Step 2: Register in router.py**

```python
from app.api.v1.routes import scorecard
api_router.include_router(scorecard.router, tags=["scorecard"])
```

**Step 3: Commit**

```bash
git add apps/api/app/api/v1/routes/scorecard.py apps/api/app/api/v1/router.py
git commit -m "feat(api): add GET /projects/{project_id}/scorecard endpoint with scoring formulas"
```

---

### Task 14: Scorecard Visualization on Project Overview

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.module.css`

**Step 1: Add scorecard API method**

```typescript
// Add to a new scorecard section in api object
scorecard: {
  get: (orgId: string, projectId: string) =>
    request<any>(`/organizations/${orgId}/projects/${projectId}/scorecard`),
},
```

**Step 2: Fetch scorecard on project overview**

Add to the `Promise.all` in the useEffect:
```typescript
api.scorecard.get(org_id, project_id),
```

Store in state:
```typescript
const [scorecard, setScorecard] = useState<any>(null);
```

**Step 3: Add scorecard visualization above the existing score cards**

```tsx
{scorecard && (
  <div className={s.scorecardBanner}>
    <div className={s.gradeRing} data-grade={scorecard.grade[0]}>
      <span className={s.gradeValue}>{scorecard.grade}</span>
      <span className={s.gradeLabel}>Grade</span>
    </div>
    <div className={s.scoreBreakdown}>
      <div className={s.scoreRow}>
        <span className={s.scoreRowLabel}>Overall</span>
        <div className={s.scoreBar}><div className={s.scoreBarFill} style={{ width: `${scorecard.overall_score}%` }} /></div>
        <span className={s.scoreRowValue}>{scorecard.overall_score}</span>
      </div>
      <div className={s.scoreRow}>
        <span className={s.scoreRowLabel}>Security</span>
        <div className={s.scoreBar}><div className={s.scoreBarFill} style={{ width: `${scorecard.security_score}%` }} /></div>
        <span className={s.scoreRowValue}>{scorecard.security_score}</span>
      </div>
      <div className={s.scoreRow}>
        <span className={s.scoreRowLabel}>Secrets</span>
        <div className={s.scoreBar}><div className={s.scoreBarFill} style={{ width: `${scorecard.secrets_score}%` }} /></div>
        <span className={s.scoreRowValue}>{scorecard.secrets_score}</span>
      </div>
      <div className={s.scoreRow}>
        <span className={s.scoreRowLabel}>Dependencies</span>
        <div className={s.scoreBar}><div className={s.scoreBarFill} style={{ width: `${scorecard.dependency_score}%` }} /></div>
        <span className={s.scoreRowValue}>{scorecard.dependency_score}</span>
      </div>
    </div>
    <div className={s.scorecardMeta}>
      <div className={s.metaItem}>
        <span className={s.metaValue}>{scorecard.new_this_week}</span>
        <span className={s.metaLabel}>New This Week</span>
      </div>
      <div className={s.metaItem}>
        <span className={s.metaValue}>{scorecard.fixed_30d}</span>
        <span className={s.metaLabel}>Fixed (30d)</span>
      </div>
      <div className={s.metaItem}>
        <span className={s.metaValue}>{scorecard.scan_count}</span>
        <span className={s.metaLabel}>Total Scans</span>
      </div>
    </div>
  </div>
)}
```

**Step 4: Add scorecard CSS**

Append to `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.module.css`:

```css
.scorecardBanner {
  display: grid; grid-template-columns: auto 1fr auto; gap: 24px; align-items: center;
  padding: 20px 24px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-lg); margin-bottom: 16px;
}
.gradeRing {
  width: 72px; height: 72px; border-radius: 50%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; border: 3px solid var(--green);
}
.gradeRing[data-grade="A"] { border-color: var(--green); }
.gradeRing[data-grade="B"] { border-color: var(--accent); }
.gradeRing[data-grade="C"] { border-color: var(--amber); }
.gradeRing[data-grade="D"] { border-color: #fb923c; }
.gradeRing[data-grade="F"] { border-color: var(--red); }
.gradeValue { font-size: 22px; font-weight: 800; line-height: 1; }
.gradeLabel { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.scoreBreakdown { display: flex; flex-direction: column; gap: 8px; }
.scoreRow { display: flex; align-items: center; gap: 12px; }
.scoreRowLabel { font-size: 12px; color: var(--text-secondary); width: 90px; }
.scoreBar { flex: 1; height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; }
.scoreBarFill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--green)); border-radius: 3px; transition: width 0.5s ease-out; }
.scoreRowValue { font-size: 13px; font-weight: 600; font-family: "DM Mono", monospace; width: 40px; text-align: right; }
.scorecardMeta { display: flex; flex-direction: column; gap: 12px; padding-left: 20px; border-left: 1px solid var(--border); }
.metaItem { text-align: center; }
.metaValue { font-size: 20px; font-weight: 700; display: block; }
.metaLabel { font-size: 11px; color: var(--text-muted); }
```

**Step 5: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/
git commit -m "feat(web): add project scorecard visualization with grade ring and score bars"
```

---

## Phase 3: Finding Detail & Triage

Enhancements to the findings workflow.

---

### Task 15: Finding Age Indicator

Show how long each finding has been open with color-coded age.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.module.css`

**Step 1: Add age calculation helper**

```typescript
const findingAge = (firstSeen: string) => {
  const days = Math.floor((Date.now() - new Date(firstSeen).getTime()) / 86400000);
  let color = "var(--green)";
  if (days > 90) color = "var(--red)";
  else if (days > 30) color = "#fb923c";
  else if (days > 7) color = "var(--amber)";
  const label = days === 0 ? "today" : days === 1 ? "1d" : `${days}d`;
  return { label, color };
};
```

**Step 2: Add age column to the table after "First Seen"**

```tsx
<th>Age</th>
```

And in each row:
```tsx
<td>
  <span className={s.ageBadge} style={{ color: findingAge(f.first_seen_at).color }}>
    {findingAge(f.first_seen_at).label}
  </span>
</td>
```

**Step 3: Add CSS**

```css
.ageBadge { font-size: 12px; font-weight: 600; font-family: "DM Mono", monospace; }
```

**Step 4: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/
git commit -m "feat(web): add color-coded finding age indicator to findings table"
```

---

### Task 16: Sortable Columns on Findings Table

Allow sorting by severity, first_seen, and category.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.module.css`

**Step 1: Add sort state**

```typescript
const [sortBy, setSortBy] = useState<string>("first_seen_at");
const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

const toggleSort = (col: string) => {
  if (sortBy === col) setSortDir(sortDir === "asc" ? "desc" : "asc");
  else { setSortBy(col); setSortDir("desc"); }
};
```

**Step 2: Add client-side sorting to the findings array**

```typescript
const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

const sortedFindings = [...(findings?.items || [])].sort((a: any, b: any) => {
  let cmp = 0;
  if (sortBy === "severity") {
    cmp = (severityOrder[a.severity] ?? 5) - (severityOrder[b.severity] ?? 5);
  } else if (sortBy === "first_seen_at") {
    cmp = new Date(a.first_seen_at).getTime() - new Date(b.first_seen_at).getTime();
  } else if (sortBy === "category") {
    cmp = a.category.localeCompare(b.category);
  }
  return sortDir === "asc" ? cmp : -cmp;
});
```

**Step 3: Make headers clickable**

```tsx
<th className={s.sortable} onClick={() => toggleSort("severity")}>
  Severity {sortBy === "severity" ? (sortDir === "asc" ? "↑" : "↓") : ""}
</th>
```

Repeat for `first_seen_at` ("First Seen") and `category` ("Category").

**Step 4: Add CSS**

```css
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--accent); }
```

**Step 5: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/
git commit -m "feat(web): add client-side sortable columns to findings table"
```

---

### Task 17: Grouped View Toggle on Findings

Allow toggling between flat list and grouped-by-category view.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.module.css`

**Step 1: Add view mode state**

```typescript
const [viewMode, setViewMode] = useState<"flat" | "grouped">("flat");
```

**Step 2: Add toggle button next to the filter bar**

```tsx
<div className={s.viewToggle}>
  <button className={viewMode === "flat" ? s.viewBtnActive : s.viewBtn} onClick={() => setViewMode("flat")}>
    <List size={14} /> List
  </button>
  <button className={viewMode === "grouped" ? s.viewBtnActive : s.viewBtn} onClick={() => setViewMode("grouped")}>
    <Layers size={14} /> Grouped
  </button>
</div>
```

**Step 3: Add grouped rendering**

```typescript
const groupedFindings = sortedFindings.reduce((acc: Record<string, any[]>, f: any) => {
  const key = f.category;
  if (!acc[key]) acc[key] = [];
  acc[key].push(f);
  return acc;
}, {});
```

When `viewMode === "grouped"`, render:
```tsx
{Object.entries(groupedFindings).map(([category, items]) => (
  <div key={category} className={s.findingGroup}>
    <h4 className={s.groupTitle}>
      {category.replace(/_/g, " ")} <span className={s.groupCount}>({(items as any[]).length})</span>
    </h4>
    {/* Render same table rows for items in this group */}
  </div>
))}
```

**Step 4: Add CSS**

```css
.viewToggle { display: flex; border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
.viewBtn, .viewBtnActive {
  display: flex; align-items: center; gap: 4px; padding: 6px 12px; font-size: 12px;
  background: transparent; border: none; color: var(--text-muted); cursor: pointer;
}
.viewBtnActive { background: var(--accent-dim); color: var(--accent); }
.findingGroup { margin-bottom: 24px; }
.groupTitle { font-size: 14px; font-weight: 600; text-transform: capitalize; margin-bottom: 8px; }
.groupCount { font-weight: 400; color: var(--text-muted); }
```

**Step 5: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/
git commit -m "feat(web): add grouped-by-category view toggle to findings page"
```

---

### Task 18: Export Current Filtered Findings

Add a button to export the current filtered findings view.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/findings/page.tsx`

**Step 1: Add export handler**

```typescript
const handleExportFiltered = async (format: "csv" | "json") => {
  const params = Object.fromEntries(searchParams.entries());
  try {
    await api.exports.create(org_id, project_id, {
      export_type: "findings",
      format,
      title: `Filtered findings export - ${new Date().toISOString().slice(0, 10)}`,
      filters: params,
    });
    alert(`Export started. Check the Exports page for download.`);
  } catch (err) { console.error(err); }
};
```

**Step 2: Add export button in the page header**

```tsx
<div className={s.exportMenu}>
  <button className={s.btnGhost} onClick={() => handleExportFiltered("csv")}>
    <Download size={14} /> CSV
  </button>
  <button className={s.btnGhost} onClick={() => handleExportFiltered("json")}>
    <Download size={14} /> JSON
  </button>
</div>
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/findings/
git commit -m "feat(web): add export filtered findings as CSV/JSON from findings page"
```

---

### Task 19: Export Filter Criteria in Export Modal

The exports page modal doesn't expose the `filter_criteria_json` field. Add filter inputs.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/exports/page.tsx`

**Step 1: Extend form state with filter fields**

```typescript
const [form, setForm] = useState({
  export_type: "findings",
  format: "csv",
  title: "",
  filters: { severity: "", category: "", status: "" },
});
```

**Step 2: Add filter dropdowns to the modal form**

After the title input:
```tsx
<label>Severity Filter (optional)</label>
<select value={form.filters.severity} onChange={(e) => setForm({ ...form, filters: { ...form.filters, severity: e.target.value } })}>
  <option value="">All</option>
  <option value="critical">Critical</option>
  <option value="high">High</option>
  <option value="medium">Medium</option>
  <option value="low">Low</option>
</select>

<label>Category Filter (optional)</label>
<select value={form.filters.category} onChange={(e) => setForm({ ...form, filters: { ...form.filters, category: e.target.value } })}>
  <option value="">All</option>
  <option value="vulnerability">Vulnerability</option>
  <option value="secret">Secret</option>
  <option value="dependency_outdated">Dependency</option>
</select>

<label>Status Filter (optional)</label>
<select value={form.filters.status} onChange={(e) => setForm({ ...form, filters: { ...form.filters, status: e.target.value } })}>
  <option value="">All</option>
  <option value="open">Open</option>
  <option value="fixed">Fixed</option>
  <option value="suppressed">Suppressed</option>
</select>
```

**Step 3: Pass non-empty filters in the create call**

```typescript
const filters = Object.fromEntries(
  Object.entries(form.filters).filter(([_, v]) => v !== "")
);
await api.exports.create(org_id, project_id, {
  export_type: form.export_type,
  format: form.format,
  title: form.title || undefined,
  filters: Object.keys(filters).length > 0 ? filters : undefined,
});
```

**Step 4: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/exports/
git commit -m "feat(web): add filter criteria (severity, category, status) to export creation modal"
```

---

### Task 20: Export Expiration Indicator

Show when each export expires and warn if near expiration.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/exports/page.tsx`

**Step 1: Add expiration display in each export row**

After the download button:
```tsx
{exp.expires_at && (
  <span className={s.expiry} data-urgent={new Date(exp.expires_at) < new Date(Date.now() + 86400000 * 3) ? "true" : "false"}>
    Expires {new Date(exp.expires_at).toLocaleDateString()}
  </span>
)}
```

**Step 2: Add CSS**

```css
.expiry { font-size: 11px; color: var(--text-muted); }
.expiry[data-urgent="true"] { color: var(--amber); }
```

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/exports/
git commit -m "feat(web): show export expiration date with urgency indicator"
```

---

## Phase 4: Scan Lifecycle

---

### Task 21: Scan Detail Page

Create a dedicated scan detail view showing scanner runs, artifacts, and finding summary.

**Files:**
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/[scan_id]/page.module.css`

**Step 1: Create the scan detail page**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Clock, GitBranch, GitCommit, CheckCircle, XCircle, Loader, AlertTriangle, Download, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import s from "./page.module.css";

export default function ScanDetailPage() {
  const { org_id, project_id, scan_id } = useParams<{ org_id: string; project_id: string; scan_id: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.scans.get(org_id, project_id, scan_id).then((data) => {
      setScan(data);
      setLoading(false);
    });
  }, [scan_id]);

  // Poll for updates if scan is running
  useEffect(() => {
    if (!scan || !["queued", "running"].includes(scan.status)) return;
    const interval = setInterval(async () => {
      const updated = await api.scans.get(org_id, project_id, scan_id);
      setScan(updated);
      if (!["queued", "running"].includes(updated.status)) clearInterval(interval);
    }, 5000);
    return () => clearInterval(interval);
  }, [scan?.status]);

  const StatusIcon = ({ status }: { status: string }) => {
    switch (status) {
      case "completed": return <CheckCircle size={16} className={s.iconGreen} />;
      case "failed": return <XCircle size={16} className={s.iconRed} />;
      case "running": return <Loader size={16} className={s.iconSpin} />;
      case "canceled": return <AlertTriangle size={16} className={s.iconAmber} />;
      default: return <Clock size={16} className={s.iconMuted} />;
    }
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return "—";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const handleRerun = async () => {
    try {
      const newScan = await api.scans.create(org_id, project_id, {
        repository_id: scan.repository_id,
        trigger_type: "manual",
        branch_name: scan.branch_name,
      });
      router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${newScan.id}`);
    } catch (err) { console.error(err); }
  };

  if (loading) return <div className={s.loading}>Loading scan details…</div>;
  if (!scan) return <div className={s.loading}>Scan not found</div>;

  const summary = scan.summary_json || {};

  return (
    <div>
      <button className={s.backBtn} onClick={() => router.back()}>
        <ArrowLeft size={14} /> Back to Scans
      </button>

      <div className={s.header}>
        <div className={s.headerLeft}>
          <StatusIcon status={scan.status} />
          <div>
            <h1 className={s.title}>Scan <code>{scan.id.slice(0, 8)}</code></h1>
            <div className={s.meta}>
              <span><GitBranch size={12} /> {scan.branch_name || "default"}</span>
              {scan.commit_sha && <span><GitCommit size={12} /> {scan.commit_sha.slice(0, 8)}</span>}
              <span>{scan.trigger_type}</span>
              <span>{new Date(scan.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>
        <div className={s.headerActions}>
          {scan.status === "failed" && (
            <button className={s.btnPrimary} onClick={handleRerun}>
              <RefreshCw size={14} /> Re-run
            </button>
          )}
          <span className={s.statusBadge} data-status={scan.status}>{scan.status}</span>
        </div>
      </div>

      {/* Summary cards */}
      {scan.status === "completed" && (
        <div className={s.summaryGrid}>
          <div className={s.summaryCard}>
            <span className={s.summaryValue}>{summary.finding_count ?? 0}</span>
            <span className={s.summaryLabel}>Total Findings</span>
          </div>
          <div className={s.summaryCard}>
            <span className={s.summaryValue} style={{ color: "var(--red)" }}>{summary.critical_count ?? 0}</span>
            <span className={s.summaryLabel}>Critical</span>
          </div>
          <div className={s.summaryCard}>
            <span className={s.summaryValue} style={{ color: "#fb923c" }}>{summary.high_count ?? 0}</span>
            <span className={s.summaryLabel}>High</span>
          </div>
          <div className={s.summaryCard}>
            <span className={s.summaryValue}>{summary.duration_seconds ? `${summary.duration_seconds}s` : "—"}</span>
            <span className={s.summaryLabel}>Duration</span>
          </div>
        </div>
      )}

      {scan.error_message && (
        <div className={s.errorBanner}>
          <AlertTriangle size={16} />
          <span>{scan.error_message}</span>
        </div>
      )}

      {/* Scanner runs */}
      <h3 className={s.sectionTitle}>Scanner Runs</h3>
      <div className={s.runsList}>
        {(scan.scanner_runs || []).length === 0 && (
          <p className={s.empty}>{scan.status === "queued" ? "Waiting to start…" : "No scanner runs recorded"}</p>
        )}
        {(scan.scanner_runs || []).map((run: any) => (
          <div key={run.id} className={s.runCard}>
            <div className={s.runHeader}>
              <StatusIcon status={run.status} />
              <span className={s.runName}>{run.scanner_name}</span>
              {run.scanner_version && <span className={s.runVersion}>v{run.scanner_version}</span>}
              <span className={s.runDuration}>{formatDuration(run.duration_ms)}</span>
              <span className={s.statusBadge} data-status={run.status}>{run.status}</span>
            </div>
            {run.error_message && (
              <div className={s.runError}>{run.error_message}</div>
            )}
            {run.artifact_uri && (
              <a href={run.artifact_uri} className={s.artifactLink} target="_blank" rel="noopener noreferrer">
                <Download size={12} /> Download artifact
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Create the CSS module** (at `scans/[scan_id]/page.module.css`)

```css
.loading { padding: 40px; text-align: center; color: var(--text-muted); }
.backBtn {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px;
  color: var(--text-muted); background: none; border: none; cursor: pointer; margin-bottom: 16px;
}
.backBtn:hover { color: var(--accent); }
.header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 24px;
}
.headerLeft { display: flex; gap: 12px; align-items: flex-start; }
.title { font-size: 20px; font-weight: 700; margin-bottom: 4px; }
.title code { font-family: "DM Mono", monospace; font-size: 16px; color: var(--accent); }
.meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-muted); }
.meta span { display: flex; align-items: center; gap: 4px; }
.headerActions { display: flex; align-items: center; gap: 10px; }
.statusBadge {
  font-size: 12px; padding: 4px 10px; border-radius: var(--radius-sm); text-transform: capitalize;
  background: var(--bg-tertiary); color: var(--text-secondary);
}
.statusBadge[data-status="completed"] { background: var(--green-dim); color: var(--green); }
.statusBadge[data-status="failed"] { background: var(--red-dim); color: var(--red); }
.statusBadge[data-status="running"] { background: var(--accent-dim); color: var(--accent); }
.statusBadge[data-status="queued"] { background: var(--amber-dim); color: var(--amber); }
.statusBadge[data-status="canceled"] { background: var(--amber-dim); color: var(--amber); }
.summaryGrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
.summaryCard {
  padding: 16px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius); text-align: center;
}
.summaryValue { font-size: 24px; font-weight: 700; display: block; }
.summaryLabel { font-size: 11px; color: var(--text-muted); text-transform: uppercase; }
.errorBanner {
  display: flex; align-items: center; gap: 8px; padding: 12px 16px;
  background: var(--red-dim); border: 1px solid rgba(248,113,113,0.3);
  border-radius: var(--radius-sm); color: var(--red); font-size: 13px; margin-bottom: 24px;
}
.sectionTitle {
  font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--text-muted); margin-bottom: 12px;
}
.runsList { display: flex; flex-direction: column; gap: 8px; }
.runCard {
  padding: 14px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.runHeader { display: flex; align-items: center; gap: 10px; }
.runName { font-size: 14px; font-weight: 600; }
.runVersion { font-size: 11px; color: var(--text-muted); }
.runDuration { font-size: 12px; font-family: "DM Mono", monospace; color: var(--text-secondary); margin-left: auto; }
.runError { font-size: 12px; color: var(--red); background: var(--red-dim); padding: 8px; border-radius: 4px; margin-top: 8px; }
.artifactLink {
  display: inline-flex; align-items: center; gap: 4px; font-size: 12px;
  color: var(--accent); margin-top: 8px;
}
.artifactLink:hover { text-decoration: underline; }
.empty { color: var(--text-muted); font-size: 13px; text-align: center; padding: 20px; }
.iconGreen { color: var(--green); }
.iconRed { color: var(--red); }
.iconAmber { color: var(--amber); }
.iconMuted { color: var(--text-muted); }
.iconSpin { color: var(--accent); animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.btnPrimary {
  display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
  background: var(--accent); color: #060a12; border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600; cursor: pointer; border: none;
}
```

**Step 3: Make scan rows clickable on the scans list page**

In `scans/page.tsx`, wrap each scan row in a link or add an onClick:
```tsx
onClick={() => router.push(`/dashboard/${org_id}/projects/${project_id}/scans/${scan.id}`)}
style={{ cursor: "pointer" }}
```

**Step 4: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/scans/
git commit -m "feat(web): add Scan Detail page with scanner runs, summary, re-run, and polling"
```

---

### Task 22: Scanner-Level Status in Scan Table

Show which specific scanners ran and their individual status in the scan list.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/scans/page.tsx`

**Step 1: Fetch scan details for the list (or use summary_json)**

The scan list response already includes `summary_json` which may contain `scanners_run`. Use that to display scanner badges:

```tsx
{scan.summary_json?.scanners_run && (
  <div className={s.scannerBadges}>
    {scan.summary_json.scanners_run.map((name: string) => (
      <span key={name} className={s.scannerBadge}>{name}</span>
    ))}
  </div>
)}
```

**Step 2: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/scans/
git commit -m "feat(web): show scanner names from summary_json in scan list rows"
```

---

### Task 23: Scan Schedule Management UI

Build a section on the repositories page for managing scan schedules.

**Files:**
- Modify: `apps/web/lib/api.ts`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/ScheduleSection.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/ScheduleSection.module.css`

**Step 1: Add schedule API methods to `lib/api.ts`**

```typescript
schedules: {
  list: (orgId: string, projectId: string, repoId: string) =>
    request<any[]>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules`),
  create: (orgId: string, projectId: string, repoId: string, data: {
    repository_id: string; schedule_type: string; cron_expression?: string; scan_type?: string;
  }) =>
    request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (orgId: string, projectId: string, repoId: string, scheduleId: string, data: any) =>
    request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules/${scheduleId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  remove: (orgId: string, projectId: string, repoId: string, scheduleId: string) =>
    request<any>(`/organizations/${orgId}/projects/${projectId}/repositories/${repoId}/schedules/${scheduleId}`, {
      method: "DELETE",
    }),
},
```

**Step 2: Create `ScheduleSection.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { Calendar, Plus, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import { api } from "@/lib/api";
import s from "./ScheduleSection.module.css";

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

  useEffect(() => {
    api.schedules.list(orgId, projectId, repoId).then(setSchedules).catch(() => {});
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
    <div className={s.section}>
      <div className={s.sectionHeader}>
        <h4 className={s.sectionTitle}><Calendar size={14} /> Schedules for {repoName}</h4>
        <button className={s.addBtn} onClick={() => setShowCreate(true)}><Plus size={14} /> Add</button>
      </div>

      {schedules.length === 0 && !showCreate && (
        <p className={s.empty}>No scan schedules configured</p>
      )}

      {schedules.map((sched) => (
        <div key={sched.id} className={s.scheduleRow}>
          <button className={s.toggleBtn} onClick={() => toggleActive(sched)} title={sched.is_active ? "Disable" : "Enable"}>
            {sched.is_active ? <ToggleRight size={18} className={s.toggleOn} /> : <ToggleLeft size={18} className={s.toggleOff} />}
          </button>
          <div className={s.schedInfo}>
            <span className={s.schedType}>{sched.schedule_type}</span>
            {sched.cron_expression && <code className={s.cron}>{sched.cron_expression}</code>}
            <span className={s.schedMeta}>Scan: {sched.scan_type}</span>
          </div>
          {sched.next_run_at && <span className={s.nextRun}>Next: {new Date(sched.next_run_at).toLocaleString()}</span>}
          <button className={s.deleteBtn} onClick={() => handleDelete(sched.id)} title="Delete schedule">
            <Trash2 size={14} />
          </button>
        </div>
      ))}

      {showCreate && (
        <form onSubmit={handleCreate} className={s.createForm}>
          <select value={form.schedule_type} onChange={(e) => setForm({ ...form, schedule_type: e.target.value })}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="on_push">On Push</option>
          </select>
          <select value={form.scan_type} onChange={(e) => setForm({ ...form, scan_type: e.target.value })}>
            <option value="full">Full Scan</option>
            <option value="dependencies">Dependencies</option>
            <option value="secrets">Secrets</option>
          </select>
          {form.schedule_type !== "on_push" && (
            <input placeholder="Cron (optional)" value={form.cron_expression}
              onChange={(e) => setForm({ ...form, cron_expression: e.target.value })} />
          )}
          <div className={s.formActions}>
            <button type="button" className={s.cancelBtn} onClick={() => setShowCreate(false)}>Cancel</button>
            <button type="submit" className={s.saveBtn}>Create Schedule</button>
          </div>
        </form>
      )}
    </div>
  );
}
```

**Step 3: Create CSS module (`ScheduleSection.module.css`)**

```css
.section { margin-top: 28px; }
.sectionHeader { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.sectionTitle { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.addBtn {
  display: flex; align-items: center; gap: 4px; font-size: 12px; padding: 4px 10px;
  background: var(--accent-dim); color: var(--accent); border: 1px solid rgba(56,189,248,0.3);
  border-radius: var(--radius-sm); cursor: pointer;
}
.empty { color: var(--text-muted); font-size: 13px; }
.scheduleRow {
  display: flex; align-items: center; gap: 10px; padding: 10px;
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-sm); margin-bottom: 6px;
}
.toggleBtn { background: none; border: none; cursor: pointer; }
.toggleOn { color: var(--green); }
.toggleOff { color: var(--text-muted); }
.schedInfo { flex: 1; display: flex; align-items: center; gap: 10px; }
.schedType { font-size: 13px; font-weight: 600; text-transform: capitalize; }
.cron { font-size: 11px; font-family: "DM Mono", monospace; color: var(--text-muted); }
.schedMeta { font-size: 11px; color: var(--text-muted); }
.nextRun { font-size: 11px; color: var(--text-muted); font-family: "DM Mono", monospace; }
.deleteBtn { background: none; border: none; color: var(--text-muted); cursor: pointer; }
.deleteBtn:hover { color: var(--red); }
.createForm {
  display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  padding: 12px; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: var(--radius-sm); margin-top: 8px;
}
.createForm select, .createForm input {
  padding: 6px 10px; background: var(--bg-tertiary); border: 1px solid var(--border);
  border-radius: var(--radius-sm); color: var(--text-primary); font-size: 13px;
}
.formActions { display: flex; gap: 6px; margin-left: auto; }
.cancelBtn { padding: 6px 12px; background: transparent; border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: 12px; cursor: pointer; }
.saveBtn { padding: 6px 12px; background: var(--accent); color: #060a12; border: none; border-radius: var(--radius-sm); font-size: 12px; font-weight: 600; cursor: pointer; }
```

**Step 4: Integrate into repositories page**

In the repositories page, add an expandable schedule section per repo card. Add a "Schedules" button on each card that toggles showing the `ScheduleSection` component below the card.

**Step 5: Commit**

```bash
git add apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/
git commit -m "feat(web): add scan schedule management UI to repositories page"
```

---

### Tasks 24–27: Scan Page Remaining Features

**Task 24: Scan progress polling** — Already implemented in Task 21 (scan detail page polls every 5s for running scans). Mark complete.

**Task 25: Make scan table rows clickable** — Already implemented in Task 21 Step 3. Mark complete.

**Task 26: Re-run failed scan button** — Already implemented in Task 21 (scan detail page has re-run button for failed scans). Mark complete.

**Task 27: Scan schedule indicator on project overview**

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/page.tsx`

**Step 1: Check if any schedules exist across project repos**

After fetching repositories (add repo fetch to project overview):
```typescript
const [hasSchedules, setHasSchedules] = useState<boolean | null>(null);

useEffect(() => {
  api.repositories.list(org_id, project_id).then(async (res: any) => {
    const repos = res.items || res;
    let found = false;
    for (const r of repos.slice(0, 5)) {
      const schedules = await api.schedules.list(org_id, project_id, r.id);
      if (schedules.length > 0) { found = true; break; }
    }
    setHasSchedules(found);
  });
}, []);
```

**Step 2: Show indicator below severity pills**

```tsx
{hasSchedules === false && (
  <div className={s.scheduleWarning}>
    <AlertTriangle size={14} />
    <span>No scan schedules configured.</span>
    <a href={`/dashboard/${org_id}/projects/${project_id}/repositories`}>Set up automated scanning →</a>
  </div>
)}
{hasSchedules === true && (
  <div className={s.scheduleActive}>
    <CheckCircle size={14} />
    <span>Automated scanning is active</span>
  </div>
)}
```

**Step 3: Add CSS**

```css
.scheduleWarning {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px;
  background: var(--amber-dim); border: 1px solid rgba(251,191,36,0.3);
  border-radius: var(--radius-sm); font-size: 13px; color: var(--amber); margin-bottom: 16px;
}
.scheduleWarning a { color: var(--accent); font-weight: 500; }
.scheduleActive {
  display: flex; align-items: center; gap: 6px; font-size: 13px;
  color: var(--green); margin-bottom: 16px;
}
```

**Step 4: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/page.tsx apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/page.module.css
git commit -m "feat(web): add scan schedule status indicator on project overview"
```

---

## Phase 5: New Pages

---

### Task 28: Audit Log Page

**Files:**
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/audit-logs/page.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/audit-logs/page.module.css`
- Modify: `apps/web/app/(dashboard)/layout.tsx` (add nav item)

**Step 1: Create audit log page**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { FileText, Search, Download } from "lucide-react";
import { api } from "@/lib/api";
import s from "./page.module.css";

export default function AuditLogPage() {
  const { org_id } = useParams<{ org_id: string }>();
  const [logs, setLogs] = useState<any>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const limit = 25;

  useEffect(() => {
    setLoading(true);
    api.auditLogs.listOrg(org_id, page * limit, limit).then((data) => {
      setLogs(data);
      setLoading(false);
    });
  }, [org_id, page]);

  if (loading && !logs) return <div className={s.loading}>Loading audit logs…</div>;

  const items = logs?.items || [];
  const total = logs?.total || 0;

  return (
    <div>
      <div className={s.pageHeader}>
        <h2><FileText size={20} /> Audit Log</h2>
      </div>

      <div className={s.tableWrap}>
        <table className={s.table}>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Action</th>
              <th>Actor</th>
              <th>Target</th>
              <th>IP Address</th>
            </tr>
          </thead>
          <tbody>
            {items.map((log: any) => (
              <tr key={log.id}>
                <td className={s.mono}>{new Date(log.created_at).toLocaleString()}</td>
                <td><span className={s.actionBadge}>{log.action}</span></td>
                <td>{log.actor_user_id?.slice(0, 8) || "system"}</td>
                <td>
                  {log.target_type && <span className={s.targetType}>{log.target_type}</span>}
                  {log.target_id && <code className={s.mono}>{log.target_id.slice(0, 8)}</code>}
                </td>
                <td className={s.mono}>{log.ip_address || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={s.pagination}>
        <button disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
        <span className={s.pageInfo}>{page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</span>
        <button disabled={(page + 1) * limit >= total} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}
```

**Step 2: Create CSS module** — Follow same table patterns as findings page.

**Step 3: Add "Audit Log" nav item in layout.tsx**

After the "Settings" nav item, add:
```tsx
{ label: "Audit Log", icon: FileText, href: `/dashboard/${orgId}/audit-logs`, disabled: !orgId }
```

**Step 4: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/audit-logs/ apps/web/app/\(dashboard\)/layout.tsx
git commit -m "feat(web): add Audit Log page with filterable table and sidebar nav item"
```

---

### Task 29: Suppression Rules Management Page

**Files:**
- Create: `apps/api/app/api/v1/routes/suppression_rules.py` (if not exists)
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/suppressions/page.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/suppressions/page.module.css`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/(dashboard)/layout.tsx`

**Step 1: Create API endpoint for suppression rules**

```python
# apps/api/app/api/v1/routes/suppression_rules.py
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.policy import SuppressionRule
from app.db.session import get_db

router = APIRouter()

class SuppressionRuleCreate(BaseModel):
    rule_type: str  # "category", "severity", "path", "scanner"
    match_criteria_json: dict
    reason: str
    project_id: UUID | None = None
    repository_id: UUID | None = None
    expires_at: str | None = None

class SuppressionRuleResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str | None
    repository_id: str | None
    rule_type: str
    match_criteria_json: dict
    reason: str
    is_active: bool
    expires_at: str | None
    created_at: str
    class Config:
        from_attributes = True

@router.post("/organizations/{org_id}/suppression-rules", status_code=201)
async def create_rule(org_id: UUID, body: SuppressionRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = SuppressionRule(
        organization_id=org_id,
        project_id=body.project_id,
        repository_id=body.repository_id,
        rule_type=body.rule_type,
        match_criteria_json=body.match_criteria_json,
        reason=body.reason,
        is_active=True,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.get("/organizations/{org_id}/suppression-rules")
async def list_rules(org_id: UUID, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    total = (await db.execute(
        select(func.count()).select_from(SuppressionRule).where(SuppressionRule.organization_id == org_id)
    )).scalar_one()
    result = await db.execute(
        select(SuppressionRule).where(SuppressionRule.organization_id == org_id)
        .order_by(SuppressionRule.created_at.desc()).offset(skip).limit(limit)
    )
    rules = result.scalars().all()
    return {"items": rules, "total": total, "skip": skip, "limit": limit}

@router.patch("/organizations/{org_id}/suppression-rules/{rule_id}")
async def update_rule(org_id: UUID, rule_id: UUID, body: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SuppressionRule).where(SuppressionRule.id == rule_id, SuppressionRule.organization_id == org_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Rule not found")
    if "is_active" in body:
        rule.is_active = body["is_active"]
    if "reason" in body:
        rule.reason = body["reason"]
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/organizations/{org_id}/suppression-rules/{rule_id}", status_code=204)
async def delete_rule(org_id: UUID, rule_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SuppressionRule).where(SuppressionRule.id == rule_id, SuppressionRule.organization_id == org_id)
    )
    rule = result.scalar_one_or_none()
    if rule:
        await db.delete(rule)
        await db.commit()
```

**Step 2: Register in router.py**

```python
from app.api.v1.routes import suppression_rules
api_router.include_router(suppression_rules.router, tags=["suppression-rules"])
```

**Step 3: Add API client methods**

```typescript
suppressionRules: {
  list: (orgId: string) =>
    request<any>(`/organizations/${orgId}/suppression-rules`),
  create: (orgId: string, data: any) =>
    request<any>(`/organizations/${orgId}/suppression-rules`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (orgId: string, ruleId: string, data: any) =>
    request<any>(`/organizations/${orgId}/suppression-rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  remove: (orgId: string, ruleId: string) =>
    request<any>(`/organizations/${orgId}/suppression-rules/${ruleId}`, {
      method: "DELETE",
    }),
},
```

**Step 4: Build the suppression rules page** — Follow the same patterns as audit log page: table with create modal, toggle active, delete. Fields: rule_type selector, match criteria (category/severity/path pattern), reason, scope (org/project/repo).

**Step 5: Add nav item** — After "Exports" in the sidebar.

**Step 6: Commit**

```bash
git add apps/api/app/api/v1/routes/suppression_rules.py apps/api/app/api/v1/router.py apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/suppressions/ apps/web/app/\(dashboard\)/layout.tsx
git commit -m "feat: add suppression rules management page and API endpoints"
```

---

### Task 30: Security Scorecard Dashboard Page

A dedicated executive-level dashboard aggregating all project scores.

**Files:**
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/scorecard/page.module.css`
- Modify: `apps/web/app/(dashboard)/layout.tsx`

**Step 1: Build the scorecard dashboard**

Fetch all projects for the org, then fetch scorecard for each. Display:
- Organization-level aggregate score (average of all project scores)
- Grid of project scorecard cards showing: grade, overall score, critical/high counts
- "Top 10 Unresolved Critical" table pulling from findings API with `severity=critical&status=open&limit=10`
- MTTR placeholder (calculate from finding events if data exists)

**Step 2: Add nav item** — Add "Scorecard" to sidebar nav, after "Overview".

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/scorecard/ apps/web/app/\(dashboard\)/layout.tsx
git commit -m "feat(web): add organization-level Security Scorecard dashboard page"
```

---

### Task 31: Repository Detail Page

**Files:**
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/[repo_id]/page.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/[repo_id]/page.module.css`

**Step 1: Build the repository detail page**

Fetch repo details via `api.repositories` (add `get` method if needed), display:
- Repo metadata (provider, full name, branch, clone URL, active status)
- Integration status (GitHub App, webhook)
- Scan history filtered to this repo (fetch scans and filter by repo_id)
- Findings filtered to this repo (link to findings page with `?repositoryId=...`)
- Scan schedules (reuse ScheduleSection component from Task 23)
- Disconnect repo button

**Step 2: Make repo cards clickable on the repositories grid**

Wrap each card in a link to `/dashboard/${org_id}/projects/${project_id}/repositories/${repo.id}`.

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/
git commit -m "feat(web): add Repository Detail page with integration status, scans, and schedules"
```

---

### Task 32: User Profile Page

**Files:**
- Create: `apps/web/app/(dashboard)/profile/page.tsx`
- Create: `apps/web/app/(dashboard)/profile/page.module.css`
- Modify: `apps/web/app/(dashboard)/layout.tsx`

**Step 1: Build the profile page**

Display:
- User info section (name, email — from auth context or placeholder)
- Organization memberships list
- Notification preferences (placeholder checkboxes for future: email on critical, scan complete, etc.)

**Step 2: Wire "Sign Out" button in sidebar** — Navigate to auth signout URL or clear local state.

**Step 3: Add "Profile" to sidebar footer** — Before "Sign Out".

**Step 4: Commit**

```bash
git add apps/web/app/\(dashboard\)/profile/ apps/web/app/\(dashboard\)/layout.tsx
git commit -m "feat(web): add User Profile page with memberships and notification preferences"
```

---

### Task 33: Findings Trend Chart on Project Overview (No New Dependencies)

Build a simple SVG-based sparkline chart showing findings over time without adding chart libraries.

**Files:**
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/TrendChart.tsx`
- Create: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/TrendChart.module.css`
- Create: `apps/api/app/api/v1/routes/findings_trend.py`
- Modify: `apps/api/app/api/v1/router.py`
- Modify: `apps/web/lib/api.ts`

**Step 1: Create the trend API endpoint**

```python
# apps/api/app/api/v1/routes/findings_trend.py
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.finding import Finding
from app.db.session import get_db

router = APIRouter()

@router.get("/organizations/{org_id}/projects/{project_id}/findings/trend")
async def get_findings_trend(org_id: UUID, project_id: UUID, days: int = 30, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    # Count findings created per day
    result = await db.execute(
        select(
            cast(Finding.first_seen_at, Date).label("date"),
            func.count().label("count"),
        )
        .where(Finding.project_id == project_id, Finding.first_seen_at >= start)
        .group_by(cast(Finding.first_seen_at, Date))
        .order_by(cast(Finding.first_seen_at, Date))
    )
    rows = result.all()

    # Fill in missing days
    data = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        count = next((r.count for r in rows if r.date == d), 0)
        data.append({"date": d.isoformat(), "count": count})

    return {"data": data, "days": days}
```

**Step 2: Register route**

```python
from app.api.v1.routes import findings_trend
api_router.include_router(findings_trend.router, tags=["findings"])
```

**Step 3: Add API client method**

```typescript
// Add to findings object
trend: (orgId: string, projectId: string, days = 30) =>
  request<any>(`/organizations/${orgId}/projects/${projectId}/findings/trend?days=${days}`),
```

**Step 4: Create `TrendChart.tsx`** — A pure SVG sparkline component

```tsx
"use client";

import s from "./TrendChart.module.css";

interface Props {
  data: { date: string; count: number }[];
  height?: number;
  width?: number;
}

export default function TrendChart({ data, height = 120, width = 500 }: Props) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.count), 1);
  const padY = 10;
  const padX = 4;
  const chartW = width - padX * 2;
  const chartH = height - padY * 2;

  const points = data.map((d, i) => {
    const x = padX + (i / (data.length - 1)) * chartW;
    const y = padY + chartH - (d.count / max) * chartH;
    return `${x},${y}`;
  });

  const line = points.join(" ");
  const area = `${padX},${padY + chartH} ${line} ${padX + chartW},${padY + chartH}`;

  return (
    <div className={s.chart}>
      <svg viewBox={`0 0 ${width} ${height}`} className={s.svg}>
        <polygon points={area} fill="rgba(56, 189, 248, 0.1)" />
        <polyline points={line} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className={s.labels}>
        <span>{data[0]?.date}</span>
        <span>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}
```

**Step 5: Wire into project overview page**

Fetch trend data and render `<TrendChart data={trendData} />` in the two-column layout.

**Step 6: Commit**

```bash
git add apps/api/app/api/v1/routes/findings_trend.py apps/api/app/api/v1/router.py apps/web/lib/api.ts apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/TrendChart*
git commit -m "feat: add findings trend API and SVG sparkline chart on project overview"
```

---

## Phase 6: Notifications & Navigation

---

### Task 34: Notification Click-Through Navigation

Make notifications clickable to navigate to the relevant entity.

**Files:**
- Modify: `apps/web/app/(dashboard)/notifications/page.tsx`

**Step 1: Add router and click handler**

```typescript
const router = useRouter();

const handleNotifClick = (notif: any) => {
  // Mark as read
  if (!notif.is_read) {
    api.notifications.markRead([notif.id]);
  }
  // Navigate based on link field or metadata
  if (notif.link) {
    router.push(notif.link);
  }
};
```

**Step 2: Make notification items clickable**

Add `onClick={() => handleNotifClick(n)}` and `style={{ cursor: n.link ? "pointer" : "default" }}` to each notification item.

**Step 3: Commit**

```bash
git add apps/web/app/\(dashboard\)/notifications/
git commit -m "feat(web): make notifications clickable with navigation to target entity"
```

---

### Task 35: Notification Unread Badge in Sidebar

Show unread count on the notifications icon in the sidebar.

**Files:**
- Modify: `apps/web/app/(dashboard)/layout.tsx`
- Modify: `apps/web/app/(dashboard)/layout.module.css`

**Step 1: Fetch unread count**

```typescript
const [unreadCount, setUnreadCount] = useState(0);

useEffect(() => {
  api.notifications.unreadCount().then((res: any) => setUnreadCount(res.unread_count || 0)).catch(() => {});
  // Poll every 30 seconds
  const interval = setInterval(() => {
    api.notifications.unreadCount().then((res: any) => setUnreadCount(res.unread_count || 0)).catch(() => {});
  }, 30000);
  return () => clearInterval(interval);
}, []);
```

**Step 2: Show badge on notifications nav item**

```tsx
<span className={s.navLabel}>
  Notifications
  {unreadCount > 0 && <span className={s.unreadBadge}>{unreadCount > 99 ? "99+" : unreadCount}</span>}
</span>
```

**Step 3: Also show on the header notifications button**

The header already has a `.notifDot` class. Conditionally show it:
```tsx
{unreadCount > 0 && <span className={s.notifDot} />}
```

**Step 4: Add CSS for badge**

```css
.unreadBadge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
  background: var(--red); color: white; font-size: 10px; font-weight: 700;
  margin-left: 6px;
}
```

**Step 5: Commit**

```bash
git add apps/web/app/\(dashboard\)/layout.tsx apps/web/app/\(dashboard\)/layout.module.css
git commit -m "feat(web): add unread notification count badge to sidebar and header"
```

---

### Task 36: Notification Type and Severity Filters

**Files:**
- Modify: `apps/web/app/(dashboard)/notifications/page.tsx`
- Modify: `apps/web/app/(dashboard)/notifications/page.module.css`

**Step 1: Add filter state**

```typescript
const [typeFilter, setTypeFilter] = useState("");
const [unreadOnly, setUnreadOnly] = useState(false);
```

**Step 2: Pass `unreadOnly` to API call**

```typescript
api.notifications.list(page * limit, limit, unreadOnly)
```

**Step 3: Add client-side type filter**

```typescript
const filtered = items.filter((n: any) => !typeFilter || n.notification_type === typeFilter);
```

**Step 4: Add filter controls to the header**

```tsx
<div className={s.filters}>
  <select className={s.filterSelect} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
    <option value="">All Types</option>
    <option value="scan_completed">Scan Completed</option>
    <option value="secret_found">Secret Found</option>
    <option value="scan_failed">Scan Failed</option>
  </select>
  <label className={s.checkLabel}>
    <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
    Unread only
  </label>
</div>
```

**Step 5: Commit**

```bash
git add apps/web/app/\(dashboard\)/notifications/
git commit -m "feat(web): add type and unread-only filters to notifications page"
```

---

### Tasks 37–38: Remaining Notification Features

**Task 37: Per-repo finding summary on repository cards**

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/projects/[project_id]/repositories/page.tsx`

Add a finding count per repo by fetching `api.findings.list(orgId, projectId, { repositoryId: repo.id, limit: 0 })` to get the total count, or better, add a batch endpoint. For simplicity, fetch stats per-repo in a `useEffect`:

```typescript
const [repoStats, setRepoStats] = useState<Record<string, any>>({});

useEffect(() => {
  repos.forEach((r: any) => {
    api.findings.list(org_id, project_id, { repositoryId: r.id, limit: 1 }).then((res: any) => {
      setRepoStats((prev) => ({ ...prev, [r.id]: { total: res.total } }));
    });
  });
}, [repos]);
```

Display on each card: `{repoStats[repo.id]?.total ?? 0} findings`

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/projects/\[project_id\]/repositories/
git commit -m "feat(web): show finding count per repository on repo cards"
```

**Task 38: Organization activity feed**

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`

Add a "Recent Activity" section below stats cards, fetching from `api.auditLogs.listOrg(org_id, 0, 10)`:

```tsx
<div className={s.activitySection}>
  <h3 className={s.sectionTitle}>Recent Activity</h3>
  <div className={s.activityList}>
    {activity.map((log: any) => (
      <div key={log.id} className={s.activityItem}>
        <span className={s.activityAction}>{log.action}</span>
        <span className={s.activityTarget}>{log.target_type} {log.target_id?.slice(0, 8)}</span>
        <span className={s.activityTime}>{new Date(log.created_at).toLocaleString()}</span>
      </div>
    ))}
  </div>
</div>
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/
git commit -m "feat(web): add recent activity feed from audit logs on organization page"
```

---

## Phase 7: Enhancements & Polish

---

### Task 39: Org Health Badge on Dashboard Cards

Show the worst-case grade across all projects on each org card.

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/page.tsx`

Fetch org stats for each org and display a grade badge on the card. Use `api.organizations.stats(org.id)` to get aggregate data. For grade, derive from `open_findings` and `critical_findings` using simplified logic:

```typescript
const deriveGrade = (stats: any) => {
  if (!stats) return null;
  const penalty = stats.critical_findings * 25 + stats.open_findings * 3;
  const score = Math.max(0, 100 - penalty);
  if (score >= 95) return "A+";
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
};
```

Display as a colored badge on each org card.

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/dashboard/page.tsx
git commit -m "feat(web): show health grade badge on organization cards"
```

---

### Task 40: Org Page — Member Count in Header

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/page.tsx`

After displaying the org name, show member count:
```tsx
<span className={s.memberCount}>{org.members?.length || 0} members</span>
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/page.tsx
git commit -m "feat(web): show member count in organization header"
```

---

### Task 41: Org Settings — Danger Zone

**Files:**
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.tsx`
- Modify: `apps/web/app/(dashboard)/dashboard/[org_id]/settings/page.module.css`
- Modify: `apps/web/lib/api.ts`

Add `delete` method to organizations API client:
```typescript
delete: (orgId: string) =>
  request<any>(`/organizations/${orgId}`, { method: "DELETE" }),
```

Add a "Danger Zone" card at the bottom of settings:
```tsx
<div className={s.dangerCard}>
  <h3>Danger Zone</h3>
  <p>Permanently delete this organization and all its projects, repositories, and findings.</p>
  <button className={s.dangerBtn} onClick={handleDelete}>Delete Organization</button>
</div>
```

With confirmation:
```typescript
const handleDelete = async () => {
  const confirm = prompt('Type the organization slug to confirm deletion:');
  if (confirm !== org?.slug) return;
  await api.organizations.delete(org_id);
  router.push("/dashboard");
};
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/dashboard/\[org_id\]/settings/ apps/web/lib/api.ts
git commit -m "feat(web): add danger zone with org deletion to settings page"
```

---

### Tasks 42–55: Remaining Polish Items

Each of these follows the same pattern — small, targeted modifications:

**Task 42:** Org settings — webhook URL display. Show the webhook URL pattern in the Security card.

**Task 43:** Repo detail page — disconnect repo button with confirmation dialog.

**Task 44:** Org page — "Scan All Projects" button that iterates repos and triggers scans.

**Task 45:** Findings page — SARIF mention in export. Add `sarif` option to export format (requires API update to accept `sarif` format string).

**Task 46:** Export page — row count preview. Show `row_count` field from ExportResponse when available.

**Task 47:** Export page — completed exports show file size: `{(exp.size_bytes / 1024).toFixed(1)} KB`.

**Task 48:** Org dashboard — search/filter for organizations on the main dashboard page. Add a search input that filters the org list client-side by name/slug.

**Task 49:** Project overview — per-repo health mini cards showing finding counts per repository.

**Task 50:** Findings — keyboard shortcut: `j`/`k` to navigate rows, `Enter` to open drawer.

**Task 51:** Findings drawer — "Related Findings" section querying by same `category` and `repository_id`.

**Task 52:** Onboarding — inline org creation. Let users create an org directly from step 1 without navigating away.

**Task 53:** Onboarding — "What's Next" section after completion with links to advanced features.

**Task 54:** Onboarding — dismiss/skip button storing preference in localStorage.

**Task 55:** Global error toast component for API errors instead of silent failures. Create a simple toast provider using React context.

---

## Phase 8: Onboarding & Settings Completion

---

### Task 56: Onboarding Inline Org Creation

**Files:**
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`

For the `create_org` step, show an inline form instead of a "Go" link:
```tsx
{step.id === "create_org" && !step.completed && (
  <form onSubmit={handleInlineOrgCreate} className={s.inlineForm}>
    <input placeholder="Organization name" required value={orgName} onChange={(e) => setOrgName(e.target.value)} />
    <button type="submit">Create</button>
  </form>
)}
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/onboarding/
git commit -m "feat(web): add inline organization creation on onboarding page"
```

---

### Task 57: Onboarding Post-Completion "What's Next"

**Files:**
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`

After the completion banner, show next steps:
```tsx
{checklist.is_complete && (
  <div className={s.nextSteps}>
    <h3>What's Next?</h3>
    <ul>
      <li><a href={`/dashboard/${orgId}/settings`}>Configure Slack notifications</a></li>
      <li><a href={`/dashboard/${orgId}/scorecard`}>Review your security scorecard</a></li>
      <li><a href={`/dashboard/${orgId}/settings`}>Invite team members</a></li>
    </ul>
  </div>
)}
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/onboarding/
git commit -m "feat(web): add What's Next section after onboarding completion"
```

---

### Task 58: Onboarding Dismiss

**Files:**
- Modify: `apps/web/app/(dashboard)/onboarding/page.tsx`

Add dismiss button that stores in localStorage:
```typescript
const [dismissed, setDismissed] = useState(false);
useEffect(() => {
  if (localStorage.getItem("scanforge_onboarding_dismissed") === "true") setDismissed(true);
}, []);

const handleDismiss = () => {
  localStorage.setItem("scanforge_onboarding_dismissed", "true");
  setDismissed(true);
};
```

Show dismiss button in header:
```tsx
<button className={s.dismissBtn} onClick={handleDismiss}>Dismiss</button>
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/onboarding/
git commit -m "feat(web): add dismiss button to onboarding with localStorage persistence"
```

---

### Task 59: Global Error Toast

**Files:**
- Create: `apps/web/lib/toast.tsx`
- Modify: `apps/web/app/layout.tsx`
- Modify: `apps/web/lib/api.ts`

**Step 1: Create toast context and component**

```tsx
"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";

interface Toast { id: number; message: string; type: "error" | "success" | "info" }

const ToastContext = createContext<{ addToast: (msg: string, type?: Toast["type"]) => void }>({ addToast: () => {} });

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  let nextId = 0;

  const addToast = useCallback((message: string, type: Toast["type"] = "error") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div style={{ position: "fixed", bottom: 20, right: 20, zIndex: 9999, display: "flex", flexDirection: "column", gap: 8 }}>
        {toasts.map((t) => (
          <div key={t.id} style={{
            padding: "10px 16px", borderRadius: 8, fontSize: 13, maxWidth: 360,
            background: t.type === "error" ? "var(--red-dim)" : t.type === "success" ? "var(--green-dim)" : "var(--accent-dim)",
            color: t.type === "error" ? "var(--red)" : t.type === "success" ? "var(--green)" : "var(--accent)",
            border: `1px solid ${t.type === "error" ? "rgba(248,113,113,0.3)" : t.type === "success" ? "rgba(74,222,128,0.3)" : "rgba(56,189,248,0.3)"}`,
          }}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
```

**Step 2: Wrap app in toast provider**

In `apps/web/app/layout.tsx`, wrap `{children}` with `<ToastProvider>`.

**Step 3: Update API client** — Add a global error event. Components can optionally use `useToast` to show errors.

**Commit:**
```bash
git add apps/web/lib/toast.tsx apps/web/app/layout.tsx
git commit -m "feat(web): add global error toast provider for API error notifications"
```

---

### Task 60: Final Navigation Cleanup

Update the sidebar navigation to include all new pages.

**Files:**
- Modify: `apps/web/app/(dashboard)/layout.tsx`

**Final nav structure:**
```
Overview           → /dashboard
Organizations      → /dashboard (or /dashboard/{orgId})
── Scorecard       → /dashboard/{orgId}/scorecard
── Audit Log       → /dashboard/{orgId}/audit-logs
── Settings        → /dashboard/{orgId}/settings
Findings           → .../findings
Scans              → .../scans
Repositories       → .../repositories
Exports            → .../exports
Suppressions       → .../suppressions
── Notifications   → /notifications (footer)
── Profile         → /profile (footer)
── Sign Out        (footer)
```

**Commit:**
```bash
git add apps/web/app/\(dashboard\)/layout.tsx
git commit -m "feat(web): update sidebar navigation with all new pages and sections"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1–8 | Unblock core workflow: Connect Repo, Trigger Scan, Finding Drawer, Member Management |
| 2 | 9–14 | Wire stats, scorecard API, scorecard visualization |
| 3 | 15–20 | Finding detail enhancements: age, sorting, grouping, export |
| 4 | 21–27 | Scan detail page, schedule UI, scan indicators |
| 5 | 28–33 | New pages: Audit Log, Suppression Rules, Scorecard Dashboard, Repo Detail, Profile, Trend Chart |
| 6 | 34–38 | Notification improvements, repo stats, activity feed |
| 7 | 39–55 | Polish: health badges, danger zone, search, keyboard shortcuts |
| 8 | 56–60 | Onboarding completion, toast system, navigation cleanup |

**Total: 60 tasks across 8 phases**

Each phase is independently shippable. Phase 1 is highest priority — it unblocks the core user workflow.
