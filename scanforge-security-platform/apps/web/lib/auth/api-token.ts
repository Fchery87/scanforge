type LegacyTokenResponse = {
  data?: {
    token?: string | null;
  } | null;
} | null;

type SessionResponse = {
  data?: {
    session?: {
      token?: string | null;
    } | null;
  } | null;
} | null;

type ApiAuthClient = {
  getSession?: () => Promise<SessionResponse>;
  getJWTToken?: () => Promise<string | null>;
  token?: () => Promise<LegacyTokenResponse>;
};

export async function getApiAccessToken(authClient: ApiAuthClient): Promise<string | null> {
  if (typeof authClient.getSession === "function") {
    const sessionResponse = await authClient.getSession().catch(() => null);
    const sessionToken = sessionResponse?.data?.session?.token ?? null;
    if (sessionToken) {
      return sessionToken;
    }
  }

  if (typeof authClient.getJWTToken === "function") {
    return authClient.getJWTToken();
  }

  if (typeof authClient.token === "function") {
    const tokenResponse = await authClient.token().catch(() => null);
    return tokenResponse?.data?.token ?? null;
  }

  return null;
}
