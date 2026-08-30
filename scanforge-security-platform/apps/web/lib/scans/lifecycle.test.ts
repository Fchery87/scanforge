import test from "node:test";
import assert from "node:assert/strict";

import {
  deriveScanPhase,
  canRerunScan,
  canDeleteScan,
  canCancelScan,
  deriveRerunPayload,
  getArtifactAvailability,
  getScannerRunStatus,
  isStaleActiveScan,
} from "./lifecycle.ts";

test("maps running scans to active phase", () => {
  assert.equal(deriveScanPhase({ status: "running", scanner_runs: [] }), "active");
});

test("maps completed scans to completed phase", () => {
  assert.equal(deriveScanPhase({ status: "completed" }), "completed");
});

test("maps failed scans to failed phase", () => {
  assert.equal(deriveScanPhase({ status: "failed" }), "failed");
});

test("maps long-running scans to stale phase", () => {
  assert.equal(
    deriveScanPhase({
      status: "running",
      created_at: "2026-04-03T00:00:00.000Z",
    }, new Date("2026-04-03T01:01:00.000Z")),
    "stale"
  );
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

test("uses scan history download URL instead of internal artifact URI", () => {
  const result = getArtifactAvailability({
    artifact_download_url: "/api/v1/scans/s1/scanner-runs/r1/download",
    artifact_uri: "scans/s1/trivy/raw.json",
    status: "completed",
  });

  assert.deepEqual(result, {
    available: true,
    uri: "/api/v1/scans/s1/scanner-runs/r1/download",
  });
});

test("reports scanner run status correctly", () => {
  assert.deepEqual(getScannerRunStatus({ status: "completed" }), { label: "completed", variant: "success" });
});

test("marks active scans stale after one hour", () => {
  assert.equal(
    isStaleActiveScan(
      { status: "queued", created_at: "2026-04-03T00:00:00.000Z" },
      new Date("2026-04-03T01:01:00.000Z")
    ),
    true
  );
});

test("reports stale scanner run status for long-running scans", () => {
  assert.deepEqual(
    getScannerRunStatus(
      { status: "running" },
      { status: "running", created_at: "2026-04-03T00:00:00.000Z" },
      new Date("2026-04-03T01:01:00.000Z")
    ),
    { label: "stale", variant: "error" }
  );
});
