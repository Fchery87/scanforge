"""#42: a Syft run reports its package inventory so the API can judge dependency absence."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.normalizers.syft import MAX_INVENTORY_PACKAGES
from app.scanners.base import ScannerResult
from app.services.scan_orchestrator import ScanContext
from app.services.scan_pipeline.persistence import PersistenceStage

SYFT_OUTPUT = {
    "artifacts": [
        {"name": "lodash", "version": "4.17.20", "type": "npm", "locations": [{"path": "/workspace/source/package-lock.json"}]},
        {"name": "no-version", "version": "", "type": "npm"},
        {"name": "flask", "version": "3.0.0", "type": "python", "locations": []},
        "not-an-artifact",
    ]
}


def _context(tmp_path: Path, syft: ScannerResult | None) -> ScanContext:
    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch=None,
        commit_sha="a" * 40,
        job_id="job-1",
        repo_path=tmp_path,
    )
    context.attempt_id = "attempt"
    context.execution_revision = 1
    context.worker_incarnation_id = "inc"
    context.scanner_results = {"syft": syft} if syft else {}
    return context


async def _posted_runs(monkeypatch, context: ScanContext) -> dict:
    posted: dict = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def post(self, url, json=None, headers=None, timeout=None):
            posted.update(json)
            return SimpleNamespace(raise_for_status=lambda: None)

    monkeypatch.setattr("app.services.scan_pipeline.persistence.httpx.AsyncClient", FakeClient)
    await PersistenceStage("http://api", "c").complete_scan(context)
    return {run["scanner_name"]: run for run in posted["scanner_runs"]}


@pytest.mark.asyncio
async def test_successful_syft_run_carries_a_complete_inventory(monkeypatch, tmp_path):
    syft = ScannerResult(scanner_name="syft", success=True, raw_output=SYFT_OUTPUT)

    runs = await _posted_runs(monkeypatch, _context(tmp_path, syft))

    assert runs["syft"]["metadata_json"]["inventory"] == {
        "complete": True,
        "packages": [
            {"name": "lodash", "version": "4.17.20", "path": "package-lock.json"},
            {"name": "flask", "version": "3.0.0", "path": ""},
        ],
    }


@pytest.mark.asyncio
async def test_oversized_inventory_is_marked_incomplete_not_silently_truncated(monkeypatch, tmp_path):
    artifacts = [{"name": f"p{i}", "version": "1"} for i in range(MAX_INVENTORY_PACKAGES + 1)]
    syft = ScannerResult(scanner_name="syft", success=True, raw_output={"artifacts": artifacts})

    runs = await _posted_runs(monkeypatch, _context(tmp_path, syft))

    assert runs["syft"]["metadata_json"]["inventory"] == {"complete": False, "packages": []}


@pytest.mark.asyncio
async def test_failed_syft_run_reports_no_inventory(monkeypatch, tmp_path):
    syft = ScannerResult(scanner_name="syft", success=False, raw_output={}, error="boom")

    runs = await _posted_runs(monkeypatch, _context(tmp_path, syft))

    assert "inventory" not in runs["syft"]["metadata_json"]
