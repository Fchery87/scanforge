export function getNeonAuthBaseUrl(): string {
  const value =
    process.env.NEON_AUTH_BASE_URL ||
    process.env.NEXT_PUBLIC_NEON_AUTH_BASE_URL ||
    process.env.NEON_AUTH_ISSUER;

  if (!value) {
    throw new Error(
      "Missing Neon Auth base URL. Set NEON_AUTH_BASE_URL or NEXT_PUBLIC_NEON_AUTH_BASE_URL."
    );
  }

  return value;
}

