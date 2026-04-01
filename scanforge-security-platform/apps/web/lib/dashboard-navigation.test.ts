import test from "node:test";
import assert from "node:assert/strict";

import { buildDashboardNavigation } from "./dashboard-navigation.ts";

test("keeps global workspace destinations available without an org context", () => {
  const navigation = buildDashboardNavigation("/dashboard");

  assert.deepEqual(
    navigation.primary.map((item) => ({ label: item.label, disabled: item.disabled })),
    [
      { label: "Overview", disabled: false },
      { label: "Organizations", disabled: false },
      { label: "Findings", disabled: true },
      { label: "Scans", disabled: true },
      { label: "Repositories", disabled: true },
      { label: "Exports", disabled: true },
      { label: "Scorecard", disabled: true },
      { label: "Suppressions", disabled: true },
    ]
  );
});

test("enables project destinations when the route contains org and project context", () => {
  const navigation = buildDashboardNavigation(
    "/dashboard/acme/projects/platform/findings"
  );

  assert.equal(navigation.context.orgId, "acme");
  assert.equal(navigation.context.projectId, "platform");
  assert.equal(
    navigation.primary.find((item) => item.label === "Findings")?.href,
    "/dashboard/acme/projects/platform/findings"
  );
  assert.equal(
    navigation.primary.find((item) => item.label === "Suppressions")?.disabled,
    false
  );
});

test("adds organization governance links when an org is selected", () => {
  const navigation = buildDashboardNavigation("/dashboard/acme/settings");

  assert.deepEqual(
    navigation.secondary.map((item) => item.label),
    ["Audit Log", "Settings"]
  );
  assert.equal(navigation.secondary[0]?.href, "/dashboard/acme/audit-logs");
});
