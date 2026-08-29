import { test } from "vitest";
import assert from "node:assert/strict";

import {
  formatRelativeTime,
  formatScanDuration,
  summarizeExportSize,
} from "./project-surface.ts";

test("formats relative time for recent timestamps", () => {
  const now = Date.now();
  assert.equal(formatRelativeTime(new Date(now - 45_000).toISOString(), now), "just now");
  assert.equal(formatRelativeTime(new Date(now - 5 * 60_000).toISOString(), now), "5 min ago");
});

test("formats relative time for older timestamps", () => {
  const now = Date.now();
  assert.equal(formatRelativeTime(new Date(now - 3 * 60 * 60_000).toISOString(), now), "3 hours ago");
  assert.equal(formatRelativeTime(new Date(now - 2 * 24 * 60 * 60_000).toISOString(), now), "2 days ago");
});

test("formats scan duration from milliseconds or seconds", () => {
  assert.equal(formatScanDuration({ duration_ms: 950 }), "950ms");
  assert.equal(formatScanDuration({ duration_ms: 4_250 }), "4.3s");
  assert.equal(formatScanDuration({ duration_seconds: 11.2 }), "11.2s");
  assert.equal(formatScanDuration({}), "—");
});

test("formats export size as kilobytes when present", () => {
  assert.equal(summarizeExportSize(0), null);
  assert.equal(summarizeExportSize(3072), "3.0 KB");
});
