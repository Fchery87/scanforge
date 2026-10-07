import test from "node:test";
import assert from "node:assert/strict";

import { getApiAccessToken } from "./api-token.ts";

test("uses the signed API JWT instead of the opaque session token", async () => {
  const token = await getApiAccessToken({
    token: async () => ({
      data: {
        token: "opaque-session-token",
      },
    }),
  });

  assert.equal(token, null);
});

test("returns a signed token from the auth client", async () => {
  const token = await getApiAccessToken({
    token: async () => ({
      data: {
        token: "signed.jwt.for-api",
      },
    }),
  });

  assert.equal(token, "signed.jwt.for-api");
});

test("reads a flat token field when the client omits the data wrapper", async () => {
  const token = await getApiAccessToken({
    token: async () => ({
      token: "flat.jwt.value",
    }),
  });

  assert.equal(token, "flat.jwt.value");
});

test("returns null when no access token is available", async () => {
  const token = await getApiAccessToken({});

  assert.equal(token, null);
});
