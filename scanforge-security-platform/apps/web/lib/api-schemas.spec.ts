import { expect, test } from "vitest";
import { findingTrendSchema, orgStatsSchema } from "./api-schemas";

test("generated response-shaped fixtures validate", () => {
  expect(orgStatsSchema.safeParse({ project_count: 1, open_findings: 2, critical_findings: 0, scans_today: 3, scans_this_week: 4 }).success).toBe(true);
  expect(findingTrendSchema.safeParse({ days: 1, data: [{ date: "2026-11-07", count: 2 }] }).success).toBe(true);
});

test("malformed responses are rejected for advisory fallback", () => {
  expect(orgStatsSchema.safeParse({ project_count: "wrong" }).success).toBe(false);
});
