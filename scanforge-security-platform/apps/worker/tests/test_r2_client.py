from app.clients.r2 import R2Client


def test_r2_client_disables_placeholder_configuration():
    client = R2Client(
        endpoint="https://your-account.r2.cloudflarestorage.com",
        bucket="scanforge-artifacts",
        access_key_id="your-access-key",
        secret_access_key="your-secret-key",
        public_base_url="https://cdn.your-domain.com",
    )

    assert client._enabled is False


def test_r2_client_enables_real_configuration():
    client = R2Client(
        endpoint="https://abc123.r2.cloudflarestorage.com",
        bucket="scanforge-artifacts",
        access_key_id="real-access-key",
        secret_access_key="real-secret-key",
        public_base_url="https://cdn.scanforge.app",
    )

    assert client._enabled is True


def test_r2_client_allows_placeholder_public_base_url_when_core_r2_values_are_real():
    client = R2Client(
        endpoint="https://abc123.r2.cloudflarestorage.com",
        bucket="scanforge-artifacts",
        access_key_id="real-access-key",
        secret_access_key="real-secret-key",
        public_base_url="https://cdn.your-domain.com",
    )

    assert client._enabled is True
