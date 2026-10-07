type TokenResponse = {
  data?: {
    token?: string | null;
  } | null;
  token?: string | null;
} | null;

type ApiAuthClient = {
  token?: () => Promise<TokenResponse>;
};

function isSignedJwt(value: string | null | undefined): value is string {
  if (!value) return false;
  const parts = value.split(".");
  return parts.length === 3 && parts.every((part) => part.length > 0);
}

function tokenFromResponse(response: TokenResponse): string | null {
  return response?.data?.token ?? response?.token ?? null;
}

export async function getApiAccessToken(authClient: ApiAuthClient): Promise<string | null> {
  if (typeof authClient.token === "function") {
    const tokenResponse = await authClient.token().catch(() => null);
    const candidate = tokenFromResponse(tokenResponse);
    if (isSignedJwt(candidate)) {
      return candidate;
    }
  }

  if (typeof window === "undefined") {
    return null;
  }

  const response = await fetch("/api/auth/token", { credentials: "include" }).catch(() => null);
  if (!response?.ok) {
    return null;
  }
  const body = (await response.json().catch(() => null)) as TokenResponse;
  const candidate = tokenFromResponse(body);
  return isSignedJwt(candidate) ? candidate : null;
}
