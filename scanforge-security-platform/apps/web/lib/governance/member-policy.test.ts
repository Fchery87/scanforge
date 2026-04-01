import test from "node:test";
import assert from "node:assert/strict";

import { canRemoveMember } from "./member-policy.ts";

test("prevents removing the last owner", () => {
  assert.equal(canRemoveMember({ actorRole: "owner", targetRole: "owner", ownerCount: 1 }), false);
});
