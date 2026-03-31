import pytest

from app.core import security


@pytest.mark.asyncio
async def test_verify_token_uses_jwks_client_to_resolve_signing_key(monkeypatch):
    class DummySigningKey:
        key = "test-public-key"

    class DummyJWKSClient:
        def get_signing_key(self, token):
            return DummySigningKey()

    captured = {}

    def fake_decode(token, key, algorithms, audience, issuer):
        captured["token"] = token
        captured["key"] = key
        captured["algorithms"] = algorithms
        captured["audience"] = audience
        captured["issuer"] = issuer
        return {"sub": "auth0|user-123"}

    monkeypatch.setattr(security.jwt, "decode", fake_decode)

    payload = await security.verify_token("signed-token", DummyJWKSClient())

    assert payload == {"sub": "auth0|user-123"}
    assert captured["token"] == "signed-token"
    assert captured["key"] == "test-public-key"
    assert "EdDSA" in captured["algorithms"]


@pytest.mark.asyncio
async def test_decode_token_retries_without_audience_when_token_has_no_aud_claim(monkeypatch):
    class DummySigningKey:
        key = "test-public-key"

    class DummyJWKSClient:
        def get_signing_key(self, token):
            return DummySigningKey()

    decode_calls = []

    def fake_decode(token, key=None, algorithms=None, audience=None, issuer=None, options=None):
        decode_calls.append(
            {
                "token": token,
                "key": key,
                "algorithms": algorithms,
                "audience": audience,
                "issuer": issuer,
                "options": options,
            }
        )

        if len(decode_calls) == 1:
            raise security.jwt.InvalidAudienceError("Token is missing the \"aud\" claim")

        if options == {
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        }:
            return {"sub": "auth0|user-123"}

        return {"sub": "auth0|user-123"}

    monkeypatch.setattr(security.jwt, "decode", fake_decode)
    monkeypatch.setattr(security.settings, "NEON_AUTH_AUDIENCE", "scanforge-api")

    payload = await security.decode_token("signed-token", DummyJWKSClient())

    assert payload == {"sub": "auth0|user-123"}
    assert decode_calls[0]["audience"] == "scanforge-api"
    assert decode_calls[1]["options"] == {
        "verify_signature": False,
        "verify_exp": False,
        "verify_aud": False,
        "verify_iss": False,
    }
    assert decode_calls[2]["options"] == {"verify_aud": False}


@pytest.mark.asyncio
async def test_decode_token_still_rejects_mismatched_audience_claim(monkeypatch):
    class DummySigningKey:
        key = "test-public-key"

    class DummyJWKSClient:
        def get_signing_key(self, token):
            return DummySigningKey()

    def fake_decode(token, key=None, algorithms=None, audience=None, issuer=None, options=None):
        if options == {"verify_aud": False}:
            return {"sub": "auth0|user-123", "aud": "another-service"}

        if options == {
            "verify_signature": False,
            "verify_exp": False,
            "verify_aud": False,
            "verify_iss": False,
        }:
            return {"sub": "auth0|user-123", "aud": "another-service"}

        raise security.jwt.InvalidAudienceError("Audience doesn't match")

    monkeypatch.setattr(security.jwt, "decode", fake_decode)
    monkeypatch.setattr(security.settings, "NEON_AUTH_AUDIENCE", "scanforge-api")

    with pytest.raises(security.jwt.InvalidAudienceError):
        await security.decode_token("signed-token", DummyJWKSClient())


@pytest.mark.asyncio
async def test_verify_token_logs_claim_diagnostics_for_invalid_issuer_in_development(monkeypatch):
    class DummyJWKSClient:
        def get_signing_key(self, token):
            raise AssertionError("verify_token should not request JWKS when decode_token is stubbed")

    logged = {}

    async def fake_decode_token(token, jwks_client=None):
        raise security.jwt.InvalidIssuerError("Invalid issuer")

    def fake_decode_without_verification(token):
        return {
            "iss": "https://actual-issuer.example/auth",
            "aud": "scanforge-api",
            "sub": "user-123",
        }

    def fake_logger(message, *args):
        logged["message"] = message
        logged["args"] = args

    monkeypatch.setattr(security, "decode_token", fake_decode_token)
    monkeypatch.setattr(security, "_decode_without_verification", fake_decode_without_verification)
    monkeypatch.setattr(security.settings, "APP_ENV", "development")
    monkeypatch.setattr(security.settings, "NEON_AUTH_ISSUER", "https://configured-issuer.example/auth")
    monkeypatch.setattr(security.settings, "NEON_AUTH_AUDIENCE", "scanforge-api")
    monkeypatch.setattr(security.settings, "NEON_AUTH_JWKS_URL", "https://configured-issuer.example/jwks.json")
    monkeypatch.setattr(security.logger, "error", fake_logger)

    with pytest.raises(security.AuthenticationError, match="Invalid token claims: Invalid issuer"):
        await security.verify_token("signed-token", DummyJWKSClient())

    assert logged["message"] == (
        "JWT claim verification failed: claim=%s token_claims=%s configured_issuer=%s "
        "configured_audience=%s configured_jwks_url=%s"
    )
    assert logged["args"][0] == "issuer"
    assert logged["args"][1]["iss"] == "https://actual-issuer.example/auth"
    assert logged["args"][1]["aud"] == "scanforge-api"
    assert logged["args"][2] == "https://configured-issuer.example/auth"
    assert logged["args"][3] == "scanforge-api"
    assert logged["args"][4] == "https://configured-issuer.example/jwks.json"
