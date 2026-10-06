import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import FindingDrawer from "./FindingDrawer";
import { useState } from "react";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: {
  findings: { get: vi.fn(), list: vi.fn(), updateTriage: vi.fn() },
  members: { list: vi.fn() },
} }));

const finding = {
  id: "finding", title: "SQL injection", severity: "critical", status: "open",
  project_id: "project", repository_id: "repo", category: "vulnerability", description: null,
  canonical_fingerprint: "fingerprint", primary_scanner: "semgrep", confidence_score: null,
  fixed_version: null, metadata_json: null, first_seen_at: "2026-09-30", last_seen_at: "2026-09-30",
  created_at: "2026-09-30", updated_at: "2026-09-30", instances: [], references: [], events: [],
};
const props = { orgId: "org", projectId: "project", findingId: "finding", onClose: vi.fn(), onUpdate: vi.fn() };
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.findings.get).mockResolvedValue(finding);
  vi.mocked(api.members.list).mockResolvedValue({ items: [], total: 0 });
});
afterEach(cleanup);

describe("production finding drawer", () => {
  it.each(["reviewing", "to_fix", "not_observed"])("allows disposition of a %s finding", async (status) => {
    vi.mocked(api.findings.get).mockResolvedValue({ ...finding, status });
    render(<FindingDrawer {...props} />);
    await screen.findByText("SQL injection");
    expect(screen.getByText("Resolve", { selector: "button" })).toBeEnabled();
  });
  it("traps focus and returns it to the opener after dismissal", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      return <><button onClick={() => setOpen(true)}>Open finding</button>
        {open && <FindingDrawer {...props} onClose={() => setOpen(false)} />}</>;
    }
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open finding" });
    await userEvent.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "SQL injection" });
    await userEvent.tab({ shift: true });
    expect(dialog.contains(document.activeElement)).toBe(true);
    await userEvent.keyboard("{Escape}");
    await vi.waitFor(() => expect(opener).toHaveFocus());
  });

  it("shows an accessible dialog, retains triage fields, and closes with Escape", async () => {
    render(<FindingDrawer {...props} />);
    expect(await screen.findByRole("dialog", { name: "SQL injection" })).toBeInTheDocument();
    expect(screen.getByLabelText("Owner")).toBeInTheDocument();
    expect(screen.getByLabelText("Due Date")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(props.onClose).toHaveBeenCalledOnce();
  });

  it("shows request failure and retries the actual detail request", async () => {
    vi.mocked(api.findings.get).mockRejectedValueOnce(new Error("Request denied"));
    render(<FindingDrawer {...props} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Request denied");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("SQL injection")).toBeInTheDocument();
    expect(api.findings.get).toHaveBeenCalledTimes(2);
  });

  it("ignores a stale response when selection changes", async () => {
    let resolveOld: (value: typeof finding) => void = () => {};
    vi.mocked(api.findings.get).mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }));
    const { rerender } = render(<FindingDrawer {...props} />);
    vi.mocked(api.findings.get).mockResolvedValue({ ...finding, id: "new", title: "New finding" });
    rerender(<FindingDrawer {...props} findingId="new" />);
    expect(await screen.findByText("New finding")).toBeInTheDocument();
    await act(async () => resolveOld(finding));
    expect(screen.queryByText("SQL injection")).not.toBeInTheDocument();
  });

  it("allows triage on a new selection while the previous save finishes", async () => {
    let finishSave: (value: typeof finding) => void = () => {};
    vi.mocked(api.findings.updateTriage).mockImplementationOnce(() => new Promise((resolve) => { finishSave = resolve; }));
    const { rerender } = render(<FindingDrawer {...props} />);
    await screen.findByText("SQL injection");
    fireEvent.click(screen.getByText("Save Triage", { selector: "button" }));
    expect(screen.getByText("Saving…", { selector: "button" })).toBeDisabled();
    vi.mocked(api.findings.get).mockResolvedValue({ ...finding, id: "new", title: "New finding" });
    rerender(<FindingDrawer {...props} findingId="new" />);
    await screen.findByText("New finding");
    expect(screen.getByText("Save Triage", { selector: "button" })).toBeEnabled();
    await act(async () => finishSave(finding));
    expect(screen.getByText("Save Triage", { selector: "button" })).toBeEnabled();
    expect(screen.queryByText("SQL injection")).not.toBeInTheDocument();
  });
});
