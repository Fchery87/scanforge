import hashlib
import hmac

from app.core.webhook import verify_github_webhook


def test_verify_github_webhook_valid_signature():
    secret = "test-secret"
    payload = b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_github_webhook(payload, signature, secret) is True


def test_verify_github_webhook_invalid_signature():
    secret = "test-secret"
    payload = b'{"action":"opened"}'
    assert verify_github_webhook(payload, "sha256=invalid", secret) is False


def test_verify_github_webhook_empty_secret():
    assert verify_github_webhook(b"data", "sha256=abc", "") is False


def test_verify_github_webhook_missing_signature():
    assert verify_github_webhook(b"data", "", "secret") is False


def test_sync_verify_function_removed():
    from app.core import webhook as wh

    assert not hasattr(wh, "verify_github_webhook_request"), "Synchronous verify_github_webhook_request must be removed"
