import { afterEach, expect, test, vi } from "vitest";
import { api } from "./api";

vi.mock("@/lib/auth/client", () => ({ authClient: {} }));
vi.mock("@/lib/auth/api-token", () => ({ getApiAccessToken: async () => "test-token" }));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function respond(data: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(data), { status })));
  return vi.spyOn(console, "error").mockImplementation(() => {});
}

test("schedule lists accept the API array response without false drift warnings", async () => {
  const rows = [{ id: "schedule", repository_id: "repo", schedule_type: "daily", created_at: "2026-11-07" }];
  const warning = respond(rows);
  expect(await api.schedules.list("org", "project", "repo")).toEqual(rows);
  expect(warning).not.toHaveBeenCalled();
});

test("disconnected GitHub integration is a valid nullable response", async () => {
  const warning = respond(null);
  expect(await api.github.getIntegration("org")).toBeNull();
  expect(warning).not.toHaveBeenCalled();
});

test("export metadata validates the nullable download URL", async () => {
  const metadata = { id: "export", project_id: "project", export_type: "findings", format: "json", created_at: "2026-11-07", download_url: null };
  const warning = respond(metadata);
  expect(await api.exports.download("org", "project", "export")).toEqual(metadata);
  expect(warning).not.toHaveBeenCalled();
  respond({ ...metadata, download_url: 42 });
  await api.exports.download("org", "project", "export");
  expect(warning).toHaveBeenCalled();
});

test("advisory drift returns the original payload without logging request or response secrets", async () => {
  const payload = { total: "wrong", sensitive: "response-secret" };
  const warning = respond(payload);
  expect(await api.findings.list("org", "project", { search: "query-secret" })).toEqual(payload);
  expect(warning).toHaveBeenCalledOnce();
  const diagnostic = JSON.stringify(warning.mock.calls);
  expect(diagnostic).not.toContain("query-secret");
  expect(diagnostic).not.toContain("response-secret");
});

test("bodyless responses and HTTP failures retain their behavior", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  await expect(api.organizations.delete("org")).resolves.toBeUndefined();
  respond({ detail: "Forbidden" }, 403);
  await expect(api.organizations.get("org")).rejects.toMatchObject({ status: 403, message: "Forbidden" });
});
