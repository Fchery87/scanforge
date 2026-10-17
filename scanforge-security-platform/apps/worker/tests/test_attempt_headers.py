from __future__ import annotations

import pytest

from app.services.scan_pipeline.context import ScanContext


def _context(**kwargs) -> ScanContext:
    return ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha="a" * 40,
        job_id="scan-1",
        **kwargs,
    )


def test_worker_mutation_headers_bind_worker_attempt_and_revision():
    context = _context(
        attempt_id="attempt-1",
        execution_revision=7,
        worker_incarnation_id="incarnation-1",
    )

    assert context.attempt_headers("worker-secret") == {
        "X-Worker-Credential": "worker-secret",
        "X-Scan-Attempt-Id": "attempt-1",
        "X-Scan-Execution-Revision": "7",
        "X-Scan-Worker-Incarnation-Id": "incarnation-1",
    }


@pytest.mark.parametrize(
    ("attempt_id", "execution_revision", "worker_incarnation_id"),
    [(None, 1, "incarnation-1"), ("attempt-1", None, "incarnation-1"), ("attempt-1", 1, None)],
)
def test_worker_cannot_build_mutation_headers_without_complete_attempt_identity(
    attempt_id, execution_revision, worker_incarnation_id
):
    with pytest.raises(RuntimeError, match="execution attempt identity is required"):
        _context(
            attempt_id=attempt_id,
            execution_revision=execution_revision,
            worker_incarnation_id=worker_incarnation_id,
        ).attempt_headers("worker-secret")
