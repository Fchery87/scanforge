import { expect, test } from "vitest";
import { safeAuthDestination } from "./destination";

test.each(["https://evil.test", "//evil.test", "/\\evil.test", "/auth/sign-in", "/dashboard/../../auth/sign-in", "/dashboard/%5cevil"])("rejects unsafe destination %s", (value) => {
  expect(safeAuthDestination(value)).toBe("/dashboard");
});
test("retains local dashboard query", () => {
  expect(safeAuthDestination("/dashboard/org?tab=findings")).toBe("/dashboard/org?tab=findings");
});
