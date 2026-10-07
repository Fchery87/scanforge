import test from "node:test";
import assert from "node:assert/strict";

import { buildDashboardNavigation } from "./dashboard-navigation.ts";

test("keeps work destinations present and closed until an org and project exist", () => {
  const navigation = buildDashboardNavigation("/dashboard");

  assert.deepEqual(
    navigation.work.map((item) => ({ label: item.label, disabled: item.disabled })),
    [
      { label: "Overview", disabled: false },
      { label: "Organization", disabled: false },
      { label: "Open findings", disabled: true },
      { label: "Scans", disabled: true },
    ]
  );
  assert.deepEqual(navigation.setup, []);
});

test("opens the work loop from an org route when a project is already known", () => {
  const navigation = buildDashboardNavigation("/dashboard/acme", "platform");

  assert.equal(navigation.context.orgId, "acme");
  assert.equal(navigation.context.projectId, "platform");
  assert.equal(
    navigation.work.find((item) => item.label === "Open findings")?.href,
    "/dashboard/acme/projects/platform/findings"
  );
  assert.equal(
    navigation.work.find((item) => item.label === "Open findings")?.disabled,
    false
  );
});

test("keeps the project in the URL ahead of a remembered project", () => {
  const navigation = buildDashboardNavigation(
    "/dashboard/acme/projects/live/findings",
    "remembered"
  );

  assert.equal(navigation.context.projectId, "live");
  assert.equal(
    navigation.work.find((item) => item.label === "Scans")?.href,
    "/dashboard/acme/projects/live/scans"
  );
});

test("groups setup destinations separately from daily work", () => {
  const navigation = buildDashboardNavigation("/dashboard/acme/settings", "platform");

  assert.deepEqual(
    navigation.setup.map((item) => item.label),
    ["Repositories", "Suppressions", "Exports", "Audit log", "Settings"]
  );
  assert.equal(navigation.setup[3]?.href, "/dashboard/acme/audit-logs");
});
