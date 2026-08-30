import test from "node:test";
import assert from "node:assert/strict";

import { getApiAccessToken } from "./api-token.ts";

test("returns the JWT from getJWTToken when the auth client exposes it", async () => {
  const token = await getApiAccessToken({
    getSession: async () => ({
      data: {
        session: {
          token: "jwt-from-session",
        },
      },
    }),
    getJWTToken: async () => "jwt-from-getJWTToken",
  });

  assert.equal(token, "jwt-from-session");
});

test("falls back to getJWTToken when a session object is unavailable", async () => {
  const token = await getApiAccessToken({
    getSession: async () => ({
      data: null,
    }),
    getJWTToken: async () => "jwt-from-getJWTToken",
  });

  assert.equal(token, "jwt-from-getJWTToken");
});

test("falls back to the legacy token response shape when getJWTToken is unavailable", async () => {
  const token = await getApiAccessToken({
    getSession: async () => ({
      data: null,
    }),
    token: async () => ({
      data: {
        token: "legacy-token",
      },
    }),
  });

  assert.equal(token, "legacy-token");
});

test("returns null when no access token is available", async () => {
  const token = await getApiAccessToken({
    getSession: async () => ({
      data: null,
    }),
    getJWTToken: async () => null,
  });

  assert.equal(token, null);
});
