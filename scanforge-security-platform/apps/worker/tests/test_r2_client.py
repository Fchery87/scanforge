from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.clients.r2 import R2Client


def test_r2_client_uses_only_api_and_worker_credential():
    client = R2Client(
        api_base_url="https://api.scanforge.example",
        worker_credential="worker-credential",
    )

    assert client.api_base_url == "https://api.scanforge.example"
    assert client._headers == {"X-Worker-Credential": "worker-credential"}
    assert not hasattr(client, "access_key_id")
    assert not hasattr(client, "secret_access_key")


@pytest.mark.asyncio
async def test_upload_requests_exact_key_then_puts_without_worker_credential(tmp_path):
    artifact = tmp_path / "results.json"
    artifact.write_text("{}")
    client = R2Client("https://api.example", "worker-secret")

    presign_response = Mock()
    presign_response.json.return_value = {
        "key": "scan-artifacts/org-1/scan-1/trivy/results.json",
        "upload_url": "https://storage.example/exact-signed-key",
    }
    upload_response = Mock()

    http_client = AsyncMock()
    http_client.post.return_value = presign_response
    http_client.put.return_value = upload_response
    http_client.__aenter__.return_value = http_client
    http_client.__aexit__.return_value = False

    with patch("app.clients.r2.httpx.AsyncClient", return_value=http_client):
        result = await client.upload_file(
            artifact,
            "scan-artifacts/org-1/scan-1/trivy/results.json",
        )

    assert result["storage_uri"] == "scan-artifacts/org-1/scan-1/trivy/results.json"
    assert http_client.post.await_args.kwargs["headers"] == {
        "X-Worker-Credential": "worker-secret"
    }
    assert http_client.put.await_args.kwargs["headers"] == {
        "Content-Type": "application/json"
    }
    assert "worker-secret" not in str(http_client.put.await_args)


@pytest.mark.asyncio
async def test_upload_rejects_api_key_outside_tenant_scope(tmp_path):
    artifact = tmp_path / "results.json"
    artifact.write_text("{}")
    client = R2Client("https://api.example", "worker-secret")

    response = Mock()
    response.json.return_value = {
        "key": "scan-artifacts/other-org/scan-1/trivy/results.json",
        "upload_url": "https://storage.example/signed",
    }
    http_client = AsyncMock()
    http_client.post.return_value = response
    http_client.__aenter__.return_value = http_client
    http_client.__aexit__.return_value = False

    with patch("app.clients.r2.httpx.AsyncClient", return_value=http_client):
        with pytest.raises(RuntimeError, match="outside the requested tenant scope"):
            await client.upload_file(
                artifact,
                "scan-artifacts/org-1/scan-1/trivy/results.json",
            )
