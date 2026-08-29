import { test } from "vitest";
import assert from "node:assert/strict";

import { deriveCallbackState, deriveOnboardingNextActions } from "./next-step.ts";

test("recommends github connection immediately after org creation", () => {
  const actions = deriveOnboardingNextActions([
    { id: "create_org", completed: true },
    { id: "connect_github", completed: false },
  ]);

  assert.equal(actions[0]?.id, "connect_github");
});

test("preserves onboarding as a top-level route in step action URLs", () => {
  const actions = deriveOnboardingNextActions([
    {
      id: "create_org",
      completed: true,
    },
    {
      id: "connect_github",
      completed: false,
      action_url: "/onboarding?org_id=org-1&github_connected=true",
    },
  ]);

  assert.equal(actions[0]?.url, "/onboarding?org_id=org-1&github_connected=true");
});

test("marks callback as recoverable when installation and signed state exist", () => {
  assert.deepEqual(
    deriveCallbackState({ installation_id: "123", state: "signed-state" }),
    { kind: "success" }
  );
});
