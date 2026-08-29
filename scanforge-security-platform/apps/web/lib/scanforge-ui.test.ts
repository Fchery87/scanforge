import { test } from "vitest";
import assert from "node:assert/strict";

import {
  deriveRiskGrade,
  getSeverityMeta,
  getStatusMeta,
} from "./scanforge-ui.ts";

test("derives a strong grade for low-risk repository stats", () => {
  assert.equal(
    deriveRiskGrade({ critical_findings: 0, open_findings: 2 }),
    "A"
  );
});

test("derives a failing grade for critical-heavy repository stats", () => {
  assert.equal(
    deriveRiskGrade({ critical_findings: 3, open_findings: 18 }),
    "F"
  );
});

test("returns normalized severity metadata for known severities", () => {
  assert.deepEqual(getSeverityMeta("critical"), {
    key: "critical",
    label: "Critical",
    tone: "critical",
  });
});

test("falls back to neutral metadata for unknown severity values", () => {
  assert.deepEqual(getSeverityMeta("unknown"), {
    key: "unknown",
    label: "Unknown",
    tone: "neutral",
  });
});

test("returns normalized status metadata for scan and finding states", () => {
  assert.deepEqual(getStatusMeta("running"), {
    key: "running",
    label: "Running",
    tone: "primary",
  });
  assert.deepEqual(getStatusMeta("fixed"), {
    key: "fixed",
    label: "Fixed",
    tone: "success",
  });
});
