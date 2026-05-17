from __future__ import annotations

import json

import httpx

from app.services.ai_investigation.annotation import AIAnnotation

_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
_PREFIX = "ai_annotation"


class AnnotationCache:
    def __init__(self, redis_url: str, redis_token: str) -> None:
        self._url = redis_url
        self._headers = {
            "Authorization": f"Bearer {redis_token}",
            "Content-Type": "application/json",
        }

    async def get(self, fingerprint: str) -> AIAnnotation | None:
        key = f"{_PREFIX}:{fingerprint}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(self._url, headers=self._headers, json=["GET", key], timeout=5.0)
            resp.raise_for_status()
        result = resp.json().get("result")
        if result is None:
            return None
        return AIAnnotation(**json.loads(result))

    async def set(self, fingerprint: str, annotation: AIAnnotation) -> None:
        key = f"{_PREFIX}:{fingerprint}"
        value = json.dumps(annotation.to_dict())
        async with httpx.AsyncClient() as client:
            await client.post(
                self._url,
                headers=self._headers,
                json=["SET", key, value, "EX", _TTL_SECONDS],
                timeout=5.0,
            )
