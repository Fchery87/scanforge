import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient, PyJWKClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class JWKSClient:
    def __init__(self, jwks_url: str):
        self._pyjwk_client = PyJWKClient(jwks_url, cache_keys=True)
        self._jwks_url = jwks_url

    def get_signing_key(self, token: str):
        return self._pyjwk_client.get_signing_key_from_jwt(token)


@lru_cache
def get_jwks_client() -> JWKSClient:
    url = settings.NEON_AUTH_JWKS_URL
    if not url:
        raise AuthenticationError(
            "NEON_AUTH_JWKS_URL is not configured — cannot verify tokens"
        )
    logger.info("Initializing JWKS client with URL: %s", url)
    return JWKSClient(url)


def _decode_without_verification(token: str) -> dict:
    return jwt.decode(
        token,
        options={
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        },
        algorithms=["EdDSA", "ES256", "RS256"],
    )


async def decode_token(
    token: str,
    jwks_client: JWKSClient | None = None,
) -> dict:
    if jwks_client is None:
        jwks_client = get_jwks_client()

    signing_key = jwks_client.get_signing_key(token)

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA", "ES256", "RS256"],
            audience=settings.NEON_AUTH_AUDIENCE,
            issuer=settings.NEON_AUTH_ISSUER,
        )
    except jwt.InvalidAudienceError:
        if not settings.NEON_AUTH_AUDIENCE:
            raise

        unverified_claims = _decode_without_verification(token)
        if "aud" in unverified_claims:
            raise

        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA", "ES256", "RS256"],
            issuer=settings.NEON_AUTH_ISSUER,
            options={"verify_aud": False},
        )


class AuthenticationError(Exception):
    pass


def _log_claim_verification_diagnostics(token: str, claim_kind: str) -> None:
    if settings.APP_ENV == "production":
        return

    try:
        claims = _decode_without_verification(token)
    except jwt.InvalidTokenError:
        claims = {}

    logger.error(
        "JWT claim verification failed: claim=%s token_claims=%s "
        "configured_issuer=%s configured_audience=%s configured_jwks_url=%s",
        claim_kind,
        {
            "iss": claims.get("iss"),
            "aud": claims.get("aud"),
            "sub": claims.get("sub"),
        },
        settings.NEON_AUTH_ISSUER,
        settings.NEON_AUTH_AUDIENCE,
        settings.NEON_AUTH_JWKS_URL,
    )


async def verify_token(
    token: str,
    jwks_client: JWKSClient | None = None,
) -> dict:
    try:
        return await decode_token(token, jwks_client)
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("Token has expired") from e
    except jwt.InvalidAudienceError as e:
        _log_claim_verification_diagnostics(token, "audience")
        raise AuthenticationError(f"Invalid token claims: {e!s}") from e
    except jwt.InvalidIssuerError as e:
        _log_claim_verification_diagnostics(token, "issuer")
        raise AuthenticationError(f"Invalid token claims: {e!s}") from e
    except (jwt.InvalidTokenError, PyJWKClientError) as e:
        raise AuthenticationError(f"Invalid token: {e!s}") from e
