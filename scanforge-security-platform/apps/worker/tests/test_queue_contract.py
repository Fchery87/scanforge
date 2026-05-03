import pytest
from pydantic import ValidationError

from app.contracts.queue import SCAN_JOB_TYPES, QueueJob


def test_scan_queue_contract_serializes_across_runtimes():
    job = QueueJob.create("scan.secrets", {"scan_id": "scan-456"})

    restored = QueueJob.model_validate_json(job.model_dump_json())

    assert restored.job_type == "scan.secrets"
    assert restored.payload == {"scan_id": "scan-456"}
    assert "scan.dependencies" in SCAN_JOB_TYPES


def test_scan_queue_contract_requires_scan_id_for_scan_jobs():
    with pytest.raises(ValidationError, match="scan_id"):
        QueueJob.create("scan.secrets", {})
