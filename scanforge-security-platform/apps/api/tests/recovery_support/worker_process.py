"""Production worker path with only source acquisition and scanner execution substituted.

No API, persistence, normalization, lease, retry or completion method is replaced.
The synthetic Gitleaks output needs no raw artifact upload by production policy.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from app.scanners.base import ScannerResult
from app.services.scan_pipeline.execution import ScanExecutionStage
from app.worker.main import Worker
from app.worker.maintenance import run_cleanup

from app.clients.queue import QueueClient


async def fixture_source(_self, context):
    root = Path(os.environ["WORKER_WORKSPACE_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    # Evidence is captured at the external boundary, not used to drive lifecycle state.
    with (root / "contexts.jsonl").open("a") as output:
        output.write(json.dumps({key: getattr(context, key) for key in (
            "scan_id", "organization_id", "repository_id", "project_id", "commit_sha",
            "attempt_id", "execution_revision", "worker_incarnation_id",
        )}) + "\n")
    if os.environ.get("RECOVERY_BOUNDARY_MODE") == "block":
        await asyncio.Event().wait()
    if os.environ.get("RECOVERY_BOUNDARY_MODE") == "fail":
        raise RuntimeError("synthetic source boundary unavailable")
    source = root / context.attempt_id / "source"
    source.mkdir(parents=True)
    return source


async def fixture_scanners(_self, context, _job_type):
    return {"gitleaks": ScannerResult(
        scanner_name="gitleaks", success=True, version="synthetic-recovery-fixture",
        raw_output=[{"RuleID": "generic-api-key", "File": "fixture.txt", "StartLine": 1,
                     "EndLine": 1, "Commit": context.commit_sha}],
        rules_digest="a" * 64, image_digest="sha256:" + "b" * 64,
    )}


if __name__ == "__main__":
    # A short queue deadline is test configuration, not a lifecycle implementation.
    # The API execution lease keeps its production 120 second duration.
    QueueClient.visibility_timeout_ms = int(os.environ.get("RECOVERY_VISIBILITY_MS", "500"))
    if sys.argv[1] == "maintenance":
        asyncio.run(run_cleanup())
    else:
        ScanExecutionStage.prepare_repository = fixture_source
        ScanExecutionStage.run_scanners = fixture_scanners
        asyncio.run(Worker().run())
