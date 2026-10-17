import pytest
from pydantic import ValidationError

from app.contracts.queue import (
    CURRENT_QUEUE_CONTRACT_VERSION,
    SCAN_JOB_TYPES,
    QueueJob,
)


def test_scan_queue_contract_serializes_across_runtimes():
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})

    restored = QueueJob.model_validate_json(job.model_dump_json())

    assert restored.job_type == "scan.repo.full"
    assert restored.contract_version == CURRENT_QUEUE_CONTRACT_VERSION
    assert restored.payload == {"scan_id": "scan-123"}
    assert "scan.repo.diff" in SCAN_JOB_TYPES


def test_scan_queue_contract_requires_scan_id_for_scan_jobs():
    with pytest.raises(ValidationError, match="scan_id"):
        QueueJob.create("scan.repo.full", {})


def test_scan_queue_contract_rejects_unsupported_contract_version():
    with pytest.raises(ValidationError, match="contract_version"):
        QueueJob(
            contract_version="2024-01-unsupported.v0",
            job_type="scan.repo.full",
            job_id="scan-123",
            payload={"scan_id": "scan-123"},
            created_at="2026-10-16T00:00:00Z",
        )

