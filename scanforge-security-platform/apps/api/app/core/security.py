import asyncio
from functools import lru_cache

import httpx
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from app.core.config import settings


class JWKSClient:
    def __init__(self, jwks_url: str):
        self.jwks_url = jwks_url
        self._jwks: dict | None = None

    async def get_jwks(self) -> dict:
        if self._jwks is None:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url, timeout=10.0)
                response.raise_for_status()
                self._jwks = response.json()
        return self._jwks


@lru_cache
def get_jwks_client() -> JWKSClient:
    return JWKSClient(settings.NEON_AUTH_JWKS_URL)


def decode_token(
    token: str,
    jwks_client: JWKSClient | None = None,
) -> dict:
    if jwks_client is None:
        jwks_client = get_jwks_client()

    jwks = asyncio.get_event_loop().run_until_complete(jwks_client.get_jwks())

    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=settings.NEON_AUTH_AUDIENCE,
        issuer=settings.NEON_AUTH_ISSUER,
    )


class AuthenticationError(Exception):
    pass


async def verify_token(token: str) -> dict:
    try:
        return decode_token(token)
    except ExpiredSignatureError as e:
        raise AuthenticationError("Token has expired") from e
    except JWTClaimsError as e:
        raise AuthenticationError(f"Invalid token claims: {e!s}") from e
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {e!s}") from e
