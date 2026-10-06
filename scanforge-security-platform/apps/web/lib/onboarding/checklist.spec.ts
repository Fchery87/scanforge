import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../api";
import { loadOnboardingChecklist } from "./checklist";

vi.mock("../api", () => {
  class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
  return { ApiError, api: {
    users: { me: vi.fn() }, organizations: { get: vi.fn(), list: vi.fn() },
    github: { getIntegration: vi.fn() }, projects: { list: vi.fn() },
    repositories: { list: vi.fn() }, scans: { list: vi.fn() }, findings: { list: vi.fn() }, schedules: { list: vi.fn() },
  } };
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.users.me).mockResolvedValue({ id: "user", auth_provider_user_id: "auth", email: "user@example.test",
    is_active: true, created_at: "date", updated_at: "date" });
  vi.mocked(api.organizations.list).mockResolvedValue({ items: [], total: 0 });
});

describe("onboarding from authenticated resources", () => {
  it("shows organization creation when none exists", async () => {
    const checklist = await loadOnboardingChecklist();
    expect(checklist.steps[0].completed).toBe(false);
    expect(checklist.steps).toHaveLength(7);
    expect(api.projects.list).not.toHaveBeenCalled();
  });

  it("preserves authorization failure rather than treating GitHub as disconnected", async () => {
    vi.mocked(api.organizations.get).mockResolvedValue({ id: "org", name: "Organization", slug: "org",
      created_by_user_id: "user", created_at: "date", updated_at: "date" });
    vi.mocked(api.github.getIntegration).mockRejectedValue(new ApiError("Forbidden", 403));
    await expect(loadOnboardingChecklist("org")).rejects.toMatchObject({ status: 403 });
  });

  it("recognizes a missing integration and supplies the actual project action URL", async () => {
    vi.mocked(api.organizations.get).mockResolvedValue({ id: "org", name: "Organization", slug: "org",
      created_by_user_id: "user", created_at: "date", updated_at: "date" });
    vi.mocked(api.github.getIntegration).mockRejectedValue(new ApiError("Not found", 404));
    vi.mocked(api.projects.list).mockResolvedValue({ items: [], total: 0 });
    const checklist = await loadOnboardingChecklist("org");
    expect(checklist.steps[1].completed).toBe(false);
    expect(checklist.steps[2].action_url).toBe("/dashboard/org");
  });
});
