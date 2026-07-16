import { createNeonAuth } from "@neondatabase/auth/next/server";

import { getNeonAuthBaseUrl } from "./shared";

function createAuth(): ReturnType<typeof createNeonAuth> {
  const cookieSecret = process.env.NEON_AUTH_COOKIE_SECRET;
  if (!cookieSecret) {
    throw new Error(
      "Missing NEON_AUTH_COOKIE_SECRET. Generate one with `openssl rand -base64 32` and add it to your env."
    );
  }
  return createNeonAuth({
    baseUrl: getNeonAuthBaseUrl(),
    cookies: {
      secret: cookieSecret,
    },
  });
}

// Proxy defers auth instantiation until a property is first accessed.
// This allows next build to succeed without the cookie secret at build time.
export const auth: ReturnType<typeof createNeonAuth> = new Proxy(
  {} as ReturnType<typeof createNeonAuth>,
  { get: (_, prop) => createAuth()[prop as keyof ReturnType<typeof createNeonAuth>] },
);
