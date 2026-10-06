from __future__ import annotations

import pytest

from app.services.ai_investigation.annotation import AIAnnotation
from app.services.ai_investigation.stage import AIInvestigationStage
from app.services.scan_pipeline.context import ScanContext


def _make_context(findings: list[dict] | None = None) -> ScanContext:
    return ScanContext(
        scan_id="scan-001",
        organization_id="org-001",
        repository_id="repo-001",
        project_id="proj-001",
        branch="main",
        commit_sha="abc123",
        job_id="job-001",
        findings=findings or [],
    )


def _make_finding(severity: str = "high", fingerprint: str = "fp-001") -> dict:
    return {
        "canonical_fingerprint": fingerprint,
        "severity": severity,
        "category": "dependency",
        "title": f"CVE-2024-{fingerprint}",
        "primary_scanner": "trivy",
        "instance": {"package_name": "lodash", "installed_version": "4.17.0"},
        "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2024-1234"}],
    }


_FAKE_ANNOTATION = AIAnnotation(
    explanation="This is a high severity vulnerability.",
    remediation="Upgrade lodash to 4.17.21.",
    model_id="claude-haiku-4-5-20251001",
    input_tokens=100,
    output_tokens=50,
    latency_ms=200,
)


class FakeProvider:
    def __init__(self):
        self.calls: list[dict] = []

    async def investigate(self, finding: dict) -> AIAnnotation:
        self.calls.append(finding)
        return _FAKE_ANNOTATION


class FailingProvider:
    async def investigate(self, finding: dict) -> AIAnnotation:
        raise RuntimeError("model unavailable")


@pytest.mark.asyncio
async def test_stage_disabled_skips_provider(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    stage = AIInvestigationStage()
    provider = FakeProvider()
    stage._provider = provider

    ctx = _make_context([_make_finding()])
    await stage.run(ctx, job_type="scan.repo.full")

    assert provider.calls == []
    assert ctx.ai_annotated_count == 0


@pytest.mark.asyncio
async def test_stage_skips_secrets_scan_type():
    stage = AIInvestigationStage()
    provider = FakeProvider()
    stage._provider = provider

    ctx = _make_context([_make_finding()])
    await stage.run(ctx, job_type="scan.secrets")

    assert provider.calls == []
    assert ctx.ai_annotated_count == 0


@pytest.mark.asyncio
async def test_stage_annotates_findings(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    stage = AIInvestigationStage()
    provider = FakeProvider()
    stage._provider = provider
    stage._cache = None

    finding = _make_finding(severity="high")
    ctx = _make_context([finding])
    await stage.run(ctx, job_type="scan.repo.full")

    assert ctx.ai_annotated_count == 1
    assert ctx.ai_skipped_count == 0
    assert finding["instance"]["ai_annotation"]["explanation"] == _FAKE_ANNOTATION.explanation


@pytest.mark.asyncio
async def test_stage_sorts_by_severity_and_respects_cap(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_MAX_FINDINGS_PER_SCAN", "2")
    stage = AIInvestigationStage()
    provider = FakeProvider()
    stage._provider = provider
    stage._cache = None

    findings = [
        _make_finding(severity="low", fingerprint="fp-low"),
        _make_finding(severity="critical", fingerprint="fp-crit"),
        _make_finding(severity="high", fingerprint="fp-high"),
    ]
    ctx = _make_context(findings)
    await stage.run(ctx, job_type="scan.repo.full")

    assert ctx.ai_annotated_count == 2
    annotated_fps = {f["canonical_fingerprint"] for f in findings if "ai_annotation" in f.get("instance", {})}
    assert "fp-crit" in annotated_fps
    assert "fp-high" in annotated_fps
    assert "fp-low" not in annotated_fps


@pytest.mark.asyncio
async def test_stage_non_blocking_on_provider_error(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    stage = AIInvestigationStage()
    stage._provider = FailingProvider()
    stage._cache = None

    ctx = _make_context([_make_finding()])
    await stage.run(ctx, job_type="scan.repo.full")

    assert ctx.ai_skipped_count == 1
    assert ctx.ai_annotated_count == 0


@pytest.mark.asyncio
async def test_stage_empty_findings_no_calls():
    stage = AIInvestigationStage()
    provider = FakeProvider()
    stage._provider = provider

    ctx = _make_context([])
    await stage.run(ctx, job_type="scan.repo.full")

    assert provider.calls == []


@pytest.mark.asyncio
async def test_stage_uses_cache_hit(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    stage = AIInvestigationStage()
    provider = FakeProvider()
    stage._provider = provider

    class FakeCache:
        async def get(self, fingerprint: str) -> AIAnnotation:
            cached = AIAnnotation(
                explanation="Cached explanation.",
                remediation=None,
                model_id="cached-model",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                cached=True,
            )
            return cached

        async def set(self, fingerprint: str, annotation: AIAnnotation) -> None:
            pass

    stage._cache = FakeCache()

    finding = _make_finding()
    ctx = _make_context([finding])
    await stage.run(ctx, job_type="scan.repo.full")

    assert provider.calls == []
    assert ctx.ai_annotated_count == 1
    assert finding["instance"]["ai_annotation"]["cached"] is True
