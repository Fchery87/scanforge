from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.ai_investigation.annotation import AIAnnotation
from app.services.ai_investigation.cache import AnnotationCache

if TYPE_CHECKING:
    from app.services.ai_investigation.provider import AIProvider
    from app.services.scan_pipeline.context import ScanContext

_log = get_logger(__name__)

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SKIP_JOB_TYPES = {"scan.secrets"}


def _make_provider() -> AIProvider:
    name = os.environ.get("AI_PROVIDER", "anthropic").lower()
    if name == "ollama":
        from app.services.ai_investigation.ollama_provider import OllamaProvider

        return OllamaProvider()
    from app.services.ai_investigation.anthropic_provider import AnthropicProvider

    return AnthropicProvider()


class AIInvestigationStage:
    def __init__(self, redis_url: str | None = None, redis_token: str | None = None) -> None:
        self._enabled = os.environ.get("AI_ENABLED", "true").lower() == "true"
        self._max_findings = int(os.environ.get("AI_MAX_FINDINGS_PER_SCAN", "50"))
        self._provider: AIProvider | None = None
        url = redis_url or os.environ.get("UPSTASH_REDIS_REST_URL", "")
        token = redis_token or os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
        self._cache: AnnotationCache | None = AnnotationCache(url, token) if url and token else None

    def _get_provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = _make_provider()
        return self._provider

    async def run(self, context: ScanContext, job_type: str = "") -> None:
        if not self._enabled:
            _log.info("ai investigation disabled", extra={"scan_id": context.scan_id})
            return
        if job_type in _SKIP_JOB_TYPES:
            _log.info(
                f"ai investigation skipped for job_type={job_type}",
                extra={"scan_id": context.scan_id},
            )
            return
        if not context.findings:
            return

        provider = self._get_provider()
        candidates = sorted(
            context.findings,
            key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "info"), 4),
        )[: self._max_findings]

        tasks = [self._annotate_finding(provider, f) for f in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        annotated = 0
        skipped = 0
        for finding, result in zip(candidates, results, strict=False):
            if isinstance(result, BaseException):
                _log.error(
                    "ai annotation failed",
                    extra={
                        "scan_id": context.scan_id,
                        "error": str(result),
                    },
                )
                skipped += 1
            else:
                finding.setdefault("instance", {})["ai_annotation"] = result.to_dict()
                annotated += 1

        context.ai_annotated_count = annotated
        context.ai_skipped_count = skipped
        _log.info(
            f"ai investigation complete: annotated={annotated} skipped={skipped} total={len(context.findings)}",
            extra={"scan_id": context.scan_id},
        )

    async def _annotate_finding(self, provider: AIProvider, finding: dict) -> AIAnnotation:
        fingerprint = finding.get("canonical_fingerprint", "")

        if self._cache and fingerprint:
            try:
                cached = await self._cache.get(fingerprint)
                if cached is not None:
                    cached.cached = True
                    return cached
            except Exception as exc:
                _log.warning(
                    "annotation cache lookup failed",
                    extra={"error": str(exc)},
                )

        annotation = await provider.investigate(finding)

        if self._cache and fingerprint:
            try:
                await self._cache.set(fingerprint, annotation)
            except Exception as exc:
                _log.warning(
                    "annotation cache write failed",
                    extra={"error": str(exc)},
                )

        return annotation
