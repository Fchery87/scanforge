import { test } from "vitest";
import assert from "node:assert/strict";

import { deriveActionAvailability, isDestructiveActionAllowed, isUnavailableAction } from "./action-policy.ts";

test("blocks actions during loading", () => {
  assert.deepEqual(
    deriveActionAvailability({ hasSelection: false, isLoading: true, hasError: false }),
    { canAct: false, reason: "Loading" }
  );
});

test("blocks actions during error state", () => {
  assert.deepEqual(
    deriveActionAvailability({ hasSelection: false, isLoading: false, hasError: true }),
    { canAct: false, reason: "Error state" }
  );
});

test("allows actions when ready", () => {
  assert.deepEqual(
    deriveActionAvailability({ hasSelection: false, isLoading: false, hasError: false }),
    { canAct: true }
  );
});

test("prevents destructive action by non-owner", () => {
  assert.deepEqual(
    isDestructiveActionAllowed({ userRole: "member", isLastOwner: false }),
    { allowed: false, reason: "Insufficient permissions" }
  );
});

test("prevents removing the last owner", () => {
  assert.deepEqual(
    isDestructiveActionAllowed({ userRole: "owner", isLastOwner: true }),
    { allowed: false, reason: "Cannot remove the last owner" }
  );
});

test("reports unavailable integration", () => {
  assert.deepEqual(
    isUnavailableAction({ integrationConnected: false }),
    { unavailable: true, reason: "Integration not connected" }
  );
});
