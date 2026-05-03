import pytest
from pydantic import ValidationError

from app.contracts.queue import SCAN_JOB_TYPES, QueueJob


def test_scan_queue_contract_serializes_across_runtimes():
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})

    restored = QueueJob.model_validate_json(job.model_dump_json())

    assert restored.job_type == "scan.repo.full"
    assert restored.payload == {"scan_id": "scan-123"}
    assert "scan.repo.diff" in SCAN_JOB_TYPES


def test_scan_queue_contract_requires_scan_id_for_scan_jobs():
    with pytest.raises(ValidationError, match="scan_id"):
        QueueJob.create("scan.repo.full", {})
