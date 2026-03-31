from app.core.config import Settings


def test_neon_auth_settings_only_expose_verification_inputs():
    fields = Settings.model_fields

    assert "NEON_AUTH_ISSUER" in fields
    assert "NEON_AUTH_AUDIENCE" in fields
    assert "NEON_AUTH_JWKS_URL" in fields
    assert "NEON_AUTH_CLIENT_ID" not in fields
    assert "NEON_AUTH_CLIENT_SECRET" not in fields
