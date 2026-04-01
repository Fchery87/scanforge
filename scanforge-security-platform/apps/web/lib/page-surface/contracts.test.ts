import test from "node:test";
import assert from "node:assert/strict";

import { normalizeGithubIntegrationState } from "./contracts.ts";

test("maps absent github integration to disconnected state", () => {
  assert.equal(normalizeGithubIntegrationState(null).status, "disconnected");
});
