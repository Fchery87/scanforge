import hashlib
import hmac

from fastapi import HTTPException, Request, status

WEBHOOK_TOLERANCE_SECONDS = 300


def verify_github_webhook(payload: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False

    if signature.startswith("sha256="):
        expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    else:
        return False

    return hmac.compare_digest(expected, signature)


async def verify_github_webhook_async(request: Request, secret: str) -> bool:
    if not secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook secret not configured")

    signature = request.headers.get("x-hub-signature-256", "")
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")

    event = request.headers.get("x-github-event", "")

    if not event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing GitHub event")

    payload = await request.body()

    if not verify_github_webhook(payload, signature, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    return True
