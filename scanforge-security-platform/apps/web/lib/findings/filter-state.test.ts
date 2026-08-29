import { test } from "vitest";
import assert from "node:assert/strict";

import { serializeFindingsFilters } from "./filter-state.ts";

test("serializes only active findings filters", () => {
  assert.deepEqual(
    serializeFindingsFilters({ severity: "critical", status: "", repositoryId: "r1" }),
    { severity: "critical", repositoryId: "r1" }
  );
});
