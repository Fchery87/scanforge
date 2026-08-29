import { test } from "vitest";
import assert from "node:assert/strict";

import { describeSuppressionScope, formatExpiryDisplay, requiresApproval, getDeleteConfirmation, getToggleMessage } from "./rule-policy.ts";

test("labels project scoped rules clearly", () => {
  assert.equal(describeSuppressionScope({ project_id: "p1" }), "project");
});

test("labels organization scoped rules", () => {
  assert.equal(describeSuppressionScope({}), "organization");
});

test("shows no expiry when expires_at is null", () => {
  const result = formatExpiryDisplay(null);
  assert.equal(result.label, "No expiry");
  assert.equal(result.isExpired, false);
});

test("detects expired rules", () => {
  const result = formatExpiryDisplay("2020-01-01");
  assert.equal(result.isExpired, true);
});

test("project rules do not require approval by default", () => {
  assert.equal(requiresApproval({ project_id: "p1" }), false);
});

test("org rules require approval by default", () => {
  assert.equal(requiresApproval({}), true);
});

test("generates delete confirmation message", () => {
  const msg = getDeleteConfirmation({
    id: "r1", rule_type: "severity", match_criteria_json: { severity: "low" },
    reason: "test", project_id: null, is_active: true,
  });
  assert.ok(msg.includes("organization-scoped"));
});

test("generates toggle activation message", () => {
  const msg = getToggleMessage({
    id: "r1", rule_type: "severity", match_criteria_json: {},
    reason: "test", project_id: null, is_active: false,
  });
  assert.ok(msg.includes("Activating"));
});
