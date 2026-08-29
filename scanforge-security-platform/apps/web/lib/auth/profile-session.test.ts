import { test } from "vitest";
import assert from "node:assert/strict";

import { resolveProfileAuthState } from "./profile-session.ts";

test("returns pending while the auth session is still loading", () => {
  assert.equal(
    resolveProfileAuthState({
      isSessionPending: true,
      hasSession: false,
    }),
    "pending"
  );
});

test("treats an existing session as authenticated even when the client token is absent", () => {
  assert.equal(
    resolveProfileAuthState({
      isSessionPending: false,
      hasSession: true,
    }),
    "authenticated"
  );
});

test("returns unauthenticated when session loading is complete and no session exists", () => {
  assert.equal(
    resolveProfileAuthState({
      isSessionPending: false,
      hasSession: false,
    }),
    "unauthenticated"
  );
});
