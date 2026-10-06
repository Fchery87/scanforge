import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { getApiAccessToken } from "./auth/api-token";

vi.mock("@/lib/auth/client", () => ({ authClient: {} }));
vi.mock("@/lib/auth/api-token", () => ({ getApiAccessToken: vi.fn(async () => "test-token") }));

const schedule = {
  id: "schedule", repository_id: "repo", schedule_type: "daily", cron_expression: null,
  scan_type: "full", is_active: true, last_run_at: null, next_run_at: null,
  created_by_user_id: null, created_at: "2026-09-30", updated_at: "2026-09-30",
};

const finding = {
  id: "finding", project_id: "project", repository_id: "repo", category: "vulnerability", severity: "high",
  status: "open", title: "Finding", description: null, canonical_fingerprint: "fingerprint", primary_scanner: null,
  confidence_score: null, fixed_version: null, metadata_json: null, first_seen_at: "date", last_seen_at: "date",
  created_at: "date", updated_at: "date", instances: [], references: [], events: [],
};

beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("authenticated API boundary", () => {
  it("accepts a complete detail response", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify(finding)));
    expect(await api.findings.get("org", "project", "finding")).toEqual(finding);
  });

  it("rejects an absent session before fetching", async () => {
    vi.mocked(getApiAccessToken).mockResolvedValueOnce(null);
    await expect(api.findings.get("org", "project", "finding")).rejects.toMatchObject({ status: 401 });
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects malformed JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("invalid"));
    await expect(api.findings.get("org", "project", "finding")).rejects.toMatchObject({ status: 502 });
  });

  it("reports network failure", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("network"));
    await expect(api.findings.get("org", "project", "finding")).rejects.toMatchObject({ status: 503 });
  });

  it("rejects an incompatible scorecard instead of returning zero metrics", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ organization_id: "org", metrics: {} })));
    await expect(api.scorecard.get("org", "project")).rejects.toMatchObject({ status: 502 });
  });

  it("rejects malformed trend counts", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ data: [{ date: "date", count: "3" }], days: 30 })));
    await expect(api.findings.trend("org", "project")).rejects.toMatchObject({ status: 502 });
  });

  it("rejects malformed finding statistics", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ total: 1, open: "1", fixed: 0, suppressed: 0,
      by_severity: {}, by_category: {} })));
    await expect(api.findings.stats("org", "project")).rejects.toMatchObject({ status: 502 });
  });
  it("uses Bearer auth and accepts the actual array schedule contract", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([schedule])));
    expect(await api.schedules.list("org", "project", "repo")).toEqual([schedule]);
    expect(vi.mocked(fetch).mock.calls[0][1]?.headers).toMatchObject({ Authorization: "Bearer test-token" });
  });

  it("rejects malformed nested finding evidence", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ ...finding, instances: [{ scan_id: 17 }] })));
    await expect(api.findings.get("org", "project", "finding")).rejects.toMatchObject({ status: 502 });
  });

  it("rejects a 204 when a finding response is required", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.findings.get("org", "project", "finding")).rejects.toMatchObject({ status: 502 });
  });

  it("accepts 204 for deletion", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    expect(await api.schedules.remove("org", "project", "repo", "schedule")).toBeUndefined();
  });

  it.each([401, 403, 429, 500])("preserves HTTP %i without retrying mutations", async (status) => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: "invalid" }] }), { status }));
    await expect(api.schedules.remove("org", "project", "repo", "schedule")).rejects.toMatchObject({ status, message: `HTTP ${status}` });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("reports a request timeout", async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }));
    const pending = api.findings.get("org", "project", "finding");
    const assertion = expect(pending).rejects.toMatchObject({ status: 408 });
    await vi.advanceTimersByTimeAsync(15001);
    await assertion;
  });
});
