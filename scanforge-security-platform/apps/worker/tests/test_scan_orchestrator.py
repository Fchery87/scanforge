from pathlib import Path

import pytest

from app.scanners.base import ScannerResult
from app.services.scan_orchestrator import ScanContext, ScanOrchestrator


class DummyQueue:
    async def update_job_status(self, *_args, **_kwargs):
        return None


class DummyR2:
    def upload_raw_output(self, scan_id: str, scanner_name: str, output_data: dict) -> str:
        return f"https://cdn.example/scans/{scan_id}/{scanner_name}/raw_output.json"

    def upload_file(self, file_path: Path, key: str) -> dict:
        return {"storage_uri": f"https://cdn.example/{key}"}


@pytest.mark.asyncio
async def test_upload_artifacts_returns_scanner_run_updates(tmp_path: Path):
    artifact = tmp_path / "trivy-results.json"
    artifact.write_text("{}")

    orchestrator = ScanOrchestrator(queue=DummyQueue(), r2=DummyR2())
    updates = []

    async def capture_update(run_id: str, **kwargs):
        updates.append((run_id, kwargs))

    orchestrator._update_scanner_run = capture_update
    context = ScanContext(
        scan_id="scan-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha=None,
        job_id="job-1",
    )
    context.scanner_results = {
        "trivy": ScannerResult(
            scanner_name="trivy",
            success=True,
            raw_output={"Results": []},
            artifact_paths=[artifact],
        )
    }
    context.scanner_run_ids = {"trivy": "run-1"}

    uploads = await orchestrator._upload_artifacts(context)

    assert uploads["trivy_raw"] == "https://cdn.example/scans/scan-1/trivy/raw_output.json"
    assert uploads["scanner_runs"]["trivy"]["artifact_uri"] == "https://cdn.example/scans/scan-1/trivy/trivy-results.json"
    assert updates == [
        (
            "run-1",
            {
                "artifact_uri": "https://cdn.example/scans/scan-1/trivy/trivy-results.json",
                "metadata_json": {
                    "raw_output_uri": "https://cdn.example/scans/scan-1/trivy/raw_output.json",
                    "artifact_uri": "https://cdn.example/scans/scan-1/trivy/trivy-results.json",
                },
            },
        )
    ]


def test_scan_summary_uses_duration_ms():
    duration_seconds = 12.3

    summary = {
        "duration_ms": int(duration_seconds * 1000),
        "duration_seconds": round(duration_seconds, 1),
    }

    assert summary["duration_ms"] == 12300


def test_diff_scan_records_changed_files_scope():
    changed_files = ["src/app.py", "infra/main.tf"]

    summary = {
        "scope": "diff",
        "changed_files": changed_files,
    }

    assert summary["scope"] == "diff"
    assert summary["changed_files"] == changed_files
