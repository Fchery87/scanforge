from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services.scan_completion import ScanCompletionConflict, ScanCompletionService


def request(**values):
    return ScanCompletionRequest(winning_attempt_id=uuid4(), execution_revision=1, **values)


def test_completion_rejects_unknown_contract_version():
    with pytest.raises(ValidationError):
        request(contract_version=2)


def test_completion_rejects_unbounded_metadata_and_scanner_count():
    with pytest.raises(ValidationError):
        request(summary_json={"payload": "x" * 65537})
    with pytest.raises(ValidationError):
        request(scanner_runs=[{"scanner_name": "trivy", "status": "completed"}] * 8)


def test_completion_does_not_invent_comparable_provenance():
    run = SimpleNamespace(scanner_version="1.0", metadata_json={})
    assert ScanCompletionService._scanner_provenance_is_comparable(run) is False


@pytest.mark.parametrize("key", [
    "scan-artifacts/other-org/scan/trivy/raw.json",
    "scan-artifacts/org/other-scan/trivy/raw.json",
    "scan-artifacts/org/scan/trivy/../secret.json",
    "https://untrusted.example/scan-artifacts/org/scan/trivy/raw.json",
    "scan-artifacts/org/scan/gitleaks/raw.json",
])
def test_completion_rejects_artifacts_outside_owned_scan(key):
    scan = SimpleNamespace(id="scan", organization_id="org")
    data = request(artifact_uris={"trivy_raw": key})
    with pytest.raises(ScanCompletionConflict, match="artifact"):
        ScanCompletionService._validate_artifacts(scan, "org", data, {"trivy"})


def test_completion_accepts_only_scoped_registered_scanner_artifacts():
    scan = SimpleNamespace(id="scan")
    data = request(
        scanner_runs=[ScannerRunCompletion(
            scanner_name="trivy", status="completed", artifact_uri="scan-artifacts/org/scan/trivy/raw.json"
        )],
        artifact_uris={"scanner_runs": {"trivy": {"raw_output_uri": "scan-artifacts/org/scan/trivy/raw.json"}}},
    )
    ScanCompletionService._validate_artifacts(scan, "org", data, {"trivy"})


def test_metadata_cannot_override_authoritative_scanner_version():
    with pytest.raises(ValidationError, match="scanner_version"):
        ScannerRunCompletion(scanner_name="trivy", scanner_version="new", status="completed",
                             metadata_json={"scanner_version": "old"})


def test_scanner_metadata_artifact_cannot_belong_to_another_scanner():
    data = request(scanner_runs=[ScannerRunCompletion(
        scanner_name="trivy", status="completed",
        metadata_json={"raw_output_uri": "scan-artifacts/org/scan/semgrep/raw.json"},
    )])
    with pytest.raises(ScanCompletionConflict, match="scanner ownership"):
        ScanCompletionService._validate_artifacts(SimpleNamespace(id="scan"), "org", data, {"trivy", "semgrep"})


@pytest.mark.parametrize("artifacts", [
    {"scanner_runs": {"trivy": {"raw_output_uri": "scan-artifacts/org/scan/semgrep/raw.json"}}},
    {"trivy_raw": "scan-artifacts/org/scan/semgrep/raw.json"},
])
def test_artifact_alias_cannot_mislabel_scanner(artifacts):
    with pytest.raises(ScanCompletionConflict, match="scanner ownership"):
        ScanCompletionService._validate_artifacts(
            SimpleNamespace(id="scan"), "org", request(artifact_uris=artifacts), {"trivy", "semgrep"}
        )


def test_artifact_presign_requires_create_only_object_write():
    from unittest.mock import Mock
    from app.clients.r2 import R2Client
    client = R2Client("https://storage.example", "bucket", "key", "secret")
    client._s3 = Mock()
    client.generate_presigned_upload_url("scan-artifacts/org/scan/trivy/run-report.json", "application/json", immutable=True)
    params = client._s3.generate_presigned_url.call_args.kwargs["Params"]
    assert params["IfNoneMatch"] == "*"
