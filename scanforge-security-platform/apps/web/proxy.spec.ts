// @vitest-environment node
import { NextRequest, NextResponse } from "next/server";
import { afterEach, expect, test, vi } from "vitest";
const { middleware } = vi.hoisted(() => ({ middleware: vi.fn() }));
vi.mock("@/lib/auth/server", () => ({ auth: { middleware: () => middleware } }));
import proxy from "./proxy";
afterEach(() => middleware.mockReset());

test("anonymous dashboard redirect preserves pathname and query", async () => {
  middleware.mockResolvedValue(NextResponse.redirect("https://scanforge.test/auth/sign-in"));
  const response = await proxy(new NextRequest("https://scanforge.test/dashboard/org?tab=findings"));
  const destination = new URL(response.headers.get("location")!);
  expect(destination.pathname).toBe("/auth/sign-in");
  expect(destination.searchParams.get("redirectTo")).toBe("/dashboard/org?tab=findings");
});

test("authenticated requests retain the middleware response including session cookies", async () => {
  const response = NextResponse.next();
  response.cookies.set("session", "refreshed");
  middleware.mockResolvedValue(response);
  expect(await proxy(new NextRequest("https://scanforge.test/dashboard"))).toBe(response);
});

test.each(["/", "/auth/sign-in", "/api/auth/session", "/dashboard-other", "/profile-other"])("public route %s bypasses auth", async (path) => {
  const response = await proxy(new NextRequest(`https://scanforge.test${path}`));
  expect(middleware).not.toHaveBeenCalled();
  expect(response.headers.get("location")).toBeNull();
});
