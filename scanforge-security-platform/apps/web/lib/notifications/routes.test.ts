import { test } from "vitest";
import assert from "node:assert/strict";

import { resolveNotificationRoute } from "./routes.ts";

test("prefers explicit notification link when present", () => {
  assert.equal(
    resolveNotificationRoute({
      link: "/dashboard/org-1/projects/project-1/scans/scan-1",
      target_type: "scan",
      target_id: "scan-1",
      metadata_json: { org_id: "org-1", project_id: "project-1" },
    }),
    "/dashboard/org-1/projects/project-1/scans/scan-1"
  );
});

test("derives scan detail route from notification target metadata", () => {
  assert.equal(
    resolveNotificationRoute({
      target_type: "scan",
      target_id: "scan-1",
      metadata_json: { org_id: "org-1", project_id: "project-1" },
    }),
    "/dashboard/org-1/projects/project-1/scans/scan-1"
  );
});

test("returns null when route context is incomplete", () => {
  assert.equal(
    resolveNotificationRoute({
      target_type: "scan",
      target_id: "scan-1",
      metadata_json: { project_id: "project-1" },
    }),
    null
  );
});
