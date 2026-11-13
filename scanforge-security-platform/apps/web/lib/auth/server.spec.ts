import { afterEach, expect, test, vi } from "vitest";

const createNeonAuth = vi.fn(() => ({ handler: () => ({ GET: vi.fn(), POST: vi.fn() }) }));
vi.mock("@neondatabase/auth/next/server", () => ({ createNeonAuth }));
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); createNeonAuth.mockClear(); });

test("auth route imports without secrets but both handlers fail closed on invocation", async () => {
  vi.stubEnv("NEON_AUTH_COOKIE_SECRET", "");
  const route = await import("@/app/api/auth/[...path]/route");
  expect(createNeonAuth).not.toHaveBeenCalled();
  for (const handler of [route.GET, route.POST]) {
    expect(() => handler(new Request("https://scanforge.test/api/auth/session"), {})).toThrow("Missing NEON_AUTH_COOKIE_SECRET");
  }
});

test("configured auth initializes only when a handler runs", async () => {
  vi.stubEnv("NEON_AUTH_COOKIE_SECRET", "runtime-only-cookie-secret");
  vi.stubEnv("NEON_AUTH_BASE_URL", "https://auth.example.test");
  const route = await import("@/app/api/auth/[...path]/route");
  expect(createNeonAuth).not.toHaveBeenCalled();
  route.GET(new Request("https://scanforge.test/api/auth/session"), {});
  expect(createNeonAuth).toHaveBeenCalledWith({ baseUrl: "https://auth.example.test", cookies: { secret: "runtime-only-cookie-secret" } });
});
