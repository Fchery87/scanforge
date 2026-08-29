import { test } from "vitest";
import assert from "node:assert/strict";

import { resolveHomeRoute } from "./route-entry.ts";

test("sends signed-out users to sign-in", () => {
  assert.equal(resolveHomeRoute({ hasSession: false }), "/auth/sign-in");
});

test("sends authenticated users with org to their dashboard", () => {
  assert.equal(resolveHomeRoute({ hasSession: true, defaultOrgId: "org1" }), "/dashboard/org1");
});

test("sends authenticated users without org to generic dashboard", () => {
  assert.equal(resolveHomeRoute({ hasSession: true }), "/dashboard");
});
