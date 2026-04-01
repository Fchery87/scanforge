import test from "node:test";
import assert from "node:assert/strict";

import { derivePageState } from "./page-state.ts";

test("prefers explicit error over empty and ready states", () => {
  assert.deepEqual(
    derivePageState({ loading: false, error: "Failed", itemCount: 0 }),
    { kind: "error", message: "Failed" }
  );
});
