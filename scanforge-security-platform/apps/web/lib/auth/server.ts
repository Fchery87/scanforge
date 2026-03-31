import { createNeonAuth } from "@neondatabase/auth/next/server";

import { getNeonAuthBaseUrl } from "./shared";

const cookieSecret = process.env.NEON_AUTH_COOKIE_SECRET;

if (!cookieSecret) {
  throw new Error(
    "Missing NEON_AUTH_COOKIE_SECRET. Generate one with `openssl rand -base64 32` and add it to your env."
  );
}

export const auth = createNeonAuth({
  baseUrl: getNeonAuthBaseUrl(),
  cookies: {
    secret: cookieSecret,
  },
});

