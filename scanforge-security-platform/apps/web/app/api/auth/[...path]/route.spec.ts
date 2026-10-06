import { afterEach, expect, it, vi } from "vitest";
import { auth } from "@/lib/auth/server";
import { POST } from "./route";

vi.mock("@/lib/auth/server", () => ({ auth: { handler: vi.fn() } }));
afterEach(() => vi.clearAllMocks());

it.each(["sign-up/email", "sign%2dup/email"])("rejects direct %s registration before forwarding upstream", async (path) => {
  const response = await POST(new Request(`http://localhost/api/auth/${path}`, { method: "POST" }), {});
  expect(response.status).toBe(403);
  await expect(response.json()).resolves.toEqual({ error: "Private beta access is by invitation" });
  expect(auth.handler).not.toHaveBeenCalled();
});

it("forwards sign-in to the configured authentication service", async () => {
  const request = new Request("http://localhost/api/auth/sign-in/email", { method: "POST" });
  const forward = vi.fn<ReturnType<typeof auth.handler>["POST"]>().mockResolvedValue(new Response("Sign in"));
  vi.mocked(auth.handler).mockReturnValue({ GET: forward, POST: forward, PUT: forward, DELETE: forward, PATCH: forward });
  const response = await POST(request, {});
  expect(await response.text()).toBe("Sign in");
  expect(forward).toHaveBeenCalledWith(request, {});
});
