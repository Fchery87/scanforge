import test from "node:test";
import assert from "node:assert/strict";

import { deriveOnboardingNextActions } from "./next-step.ts";

test("recommends github connection immediately after org creation", () => {
  const actions = deriveOnboardingNextActions([
    { id: "create_org", completed: true },
    { id: "connect_github", completed: false },
  ]);

  assert.equal(actions[0]?.id, "connect_github");
});
