from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.scanners.base import ScannerAdapter, ScannerResult
from app.services.scan_pipeline.context import ScanContext
from app.services.scan_pipeline.execution import ScanExecutionStage


class Adapter(ScannerAdapter):
    name = "contained"
    binary_name = "contained"

    def run(self, repo_path: Path) -> ScannerResult:
        raise AssertionError("local adapter execution must not run in private-beta")

    def run_contained(self, repo_path: Path, runtime, output_directory: Path) -> ScannerResult:
        runtime.called = True
        return ScannerResult(scanner_name=self.name, success=True, raw_output={})

    def runtime_arguments(self):
        return ("/workspace/source",)

    def parse_runtime_result(self, completed, output_directory):
        raise AssertionError("fake adapter bypasses parsing")


@pytest.mark.asyncio
async def test_private_beta_scanners_use_contained_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "private-beta")
    runtime = SimpleNamespace(called=False, image="scanner@sha256:" + "a" * 64)
    registration = SimpleNamespace(adapter_factory=Adapter)
    monkeypatch.setattr(
        "app.services.scan_pipeline.execution.scanners_for_scan_type",
        lambda _scan_type: ["contained"],
    )
    monkeypatch.setattr(
        "app.services.scan_pipeline.execution.SCANNER_REGISTRY",
        {"contained": registration},
    )
    stage = ScanExecutionStage(
        r2=SimpleNamespace(),
        api_base_url="http://api",
        worker_credential="credential",
        runtime=runtime,
    )
    stage._create_scanner_run = AsyncMock(return_value=None)
    stage._load_image_manifest = AsyncMock(
        return_value={
            "scanners": {"contained": "1.0.0"},
            "assets": {},
        }
    )
    monkeypatch.setattr("app.services.scan_pipeline.execution.scanner_provenance", lambda *_args: {})
    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha=None,
        job_id="job-1",
        repo_path=tmp_path,
    )

    results = await stage.run_scanners(context, "scan.repo.full")

    assert runtime.called is True
    assert results["contained"].success is True
