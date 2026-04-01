import test from "node:test";
import assert from "node:assert/strict";

import { canBulkAction, isOverdue, getSLABadge, triageActionLabel } from "./triage-policy.ts";

test("allows bulk action on open findings", () => {
  assert.deepEqual(canBulkAction("resolve", ["open", "open"]), { allowed: true });
});

test("blocks bulk resolve when all already fixed", () => {
  const result = canBulkAction("resolve", ["fixed", "fixed"]);
  assert.equal(result.allowed, false);
});

test("detects overdue due date", () => {
  assert.equal(isOverdue("2020-01-01"), true);
});

test("returns no SLA when no due date", () => {
  assert.deepEqual(getSLABadge(null), { label: "No SLA", variant: "none" });
});

test("returns overdue badge for past due date", () => {
  const badge = getSLABadge("2020-01-01");
  assert.equal(badge.variant, "danger");
});

test("returns triage label for open status", () => {
  assert.equal(triageActionLabel("open"), "Triage");
});
