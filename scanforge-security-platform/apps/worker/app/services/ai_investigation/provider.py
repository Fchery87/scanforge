from __future__ import annotations

from typing import Protocol

from app.services.ai_investigation.annotation import AIAnnotation


class AIProvider(Protocol):
    async def investigate(self, finding: dict) -> AIAnnotation: ...
