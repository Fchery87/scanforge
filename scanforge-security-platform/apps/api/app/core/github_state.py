import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

from app.core.config import settings

STATE_TTL_SECONDS = 600


class GitHubStateError(ValueError):
    pass


def _state_secret() -> str:
    return (
        settings.GITHUB_STATE_SIGNING_SECRET
        or settings.GITHUB_WEBHOOK_SECRET
        or settings.INTERNAL_API_KEY
        or settings.GITHUB_CLIENT_SECRET
    )


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_github_state(org_id: UUID, user_id: UUID, purpose: str) -> str:
    secret = _state_secret()
    if not secret:
        raise GitHubStateError("GitHub state signing secret is not configured")

    payload = {
        "org_id": str(org_id),
        "user_id": str(user_id),
        "purpose": purpose,
        "iat": int(time.time()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).digest()
    return f"{_urlsafe_b64encode(payload_bytes)}.{_urlsafe_b64encode(signature)}"


def verify_github_state(state: str, *, org_id: UUID, user_id: UUID, purpose: str) -> None:
    secret = _state_secret()
    if not secret:
        raise GitHubStateError("GitHub state signing secret is not configured")

    try:
        encoded_payload, encoded_signature = state.split(".", 1)
        payload_bytes = _urlsafe_b64decode(encoded_payload)
        signature = _urlsafe_b64decode(encoded_signature)
        payload = json.loads(payload_bytes)
    except (ValueError, json.JSONDecodeError) as exc:
        raise GitHubStateError("Invalid GitHub state") from exc

    expected_signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise GitHubStateError("Invalid GitHub state")

    issued_at = int(payload.get("iat", 0))
    if int(time.time()) - issued_at > STATE_TTL_SECONDS:
        raise GitHubStateError("Expired GitHub state")

    if payload.get("purpose") != purpose:
        raise GitHubStateError("Invalid GitHub state purpose")
    if payload.get("org_id") != str(org_id):
        raise GitHubStateError("GitHub state organization mismatch")
    if payload.get("user_id") != str(user_id):
        raise GitHubStateError("GitHub state user mismatch")
