import test from "node:test";
import assert from "node:assert/strict";

import { deriveScanPhase, canRerunScan, canDeleteScan, canCancelScan, deriveRerunPayload, getArtifactAvailability, getScannerRunStatus } from "./lifecycle.ts";

test("maps running scans to active phase", () => {
  assert.equal(deriveScanPhase({ status: "running", scanner_runs: [] }), "active");
});

test("maps completed scans to completed phase", () => {
  assert.equal(deriveScanPhase({ status: "completed" }), "completed");
});

test("maps failed scans to failed phase", () => {
  assert.equal(deriveScanPhase({ status: "failed" }), "failed");
});

test("allows rerun for failed scans", () => {
  assert.equal(canRerunScan("failed"), true);
});

test("allows delete for queued scans", () => {
  assert.equal(canDeleteScan("queued"), true);
});

test("allows cancel for running scans", () => {
  assert.equal(canCancelScan("running"), true);
});

test("derives rerun payload from scan", () => {
  const payload = deriveRerunPayload({ repository_id: "r1", branch_name: "main" });
  assert.deepEqual(payload, { repository_id: "r1", trigger_type: "manual", branch_name: "main" });
});

test("reports artifact unavailable for failed run", () => {
  const result = getArtifactAvailability({ status: "failed" });
  assert.equal(result.available, false);
});

test("reports scanner run status correctly", () => {
  assert.deepEqual(getScannerRunStatus({ status: "completed" }), { label: "completed", variant: "success" });
});
