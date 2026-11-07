# ruff: noqa: F811, ARG001, ARG002
"""P1.7 / #43: immutable verified artifact finalization.

Seams: the worker-facing routes (`create_artifact_upload_url`,
`finalize_artifact`), the download-reference check, and completion artifact
reconciliation, all against a real session and an in-memory object store that
behaves like S3 (staging and published prefixes, no-overwrite puts).
Real disposable object storage was NOT used; see the ticket report.
"""
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from test_artifact_upload_isolation import (  # noqa: F401 - fixtures
    db_session,
    live_attempt,
    principal_for,
    seed_scan,
)

from app.api.v1.routes.internal import (
    ArtifactFinalizeRequest,
    ArtifactUploadRequest,
    ExecutionAttemptIdentity,
    create_artifact_upload_url,
    finalize_artifact,
)
from app.db.models import ScanArtifact
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services.artifact_finalization import ArtifactFinalizationService


class FakeStore:
    """Dict-backed object store with S3 semantics the service relies on."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def generate_presigned_upload_url(self, key, content_type, expires_in=300):
        return f"https://signed.example/{key}"

    def object_size(self, key):
        return len(self.objects[key]) if key in self.objects else None

    def read_object(self, key, max_bytes):
        return self.objects[key][:max_bytes]

    def put_object_if_absent(self, key, body, content_type):
        if key in self.objects:
            raise FileExistsError(key)
        self.objects[key] = body

    def delete_object(self, key):
        self.objects.pop(key, None)

    def generate_presigned_url(self, key, expires_in=300):
        return f"https://signed.example/get/{key}"


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr("app.api.v1.routes.internal._artifact_store", lambda: fake)
    return fake


BODY = json.dumps({"results": [{"id": "CVE-1"}]}, separators=(",", ":")).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def issue(session, scan_id, principal, attempt, *, body=BODY, filename="results.json", scanner="trivy"):
    request = ArtifactUploadRequest(scanner_name=scanner, filename=filename, size_bytes=len(body))
    return await create_artifact_upload_url(uuid.UUID(scan_id), request, principal, attempt, session)


async def finalize(session, scan_id, principal, attempt, artifact_id, body=BODY):
    return await finalize_artifact(
        uuid.UUID(scan_id),
        uuid.UUID(artifact_id),
        ArtifactFinalizeRequest(checksum_sha256=sha(body)),
        principal,
        attempt,
        db=session,
    )


async def ready(db_session):
    session, backend = db_session
    org, other_org, scan_id = await seed_scan(session, backend)
    principal = principal_for(uuid.UUID(org))
    attempt = await live_attempt(session, scan_id, principal)
    return session, org, other_org, scan_id, principal, attempt


@pytest.mark.asyncio
async def test_upload_goes_to_attempt_scoped_staging_and_is_recorded(db_session, store):
    session, org, _o, scan_id, principal, attempt = await ready(db_session)

    issued = await issue(session, scan_id, principal, attempt)

    assert issued["key"].startswith(f"scan-staging/{org}/{scan_id}/{attempt.attempt_id}/")
    assert not issued["key"].startswith("scan-artifacts/")
    row = await session.get(ScanArtifact, issued["artifact_id"])
    assert row.verification_state == "staged"
    assert row.attempt_id == attempt.attempt_id
    assert row.staging_uri == issued["key"]


@pytest.mark.asyncio
async def test_finalize_publishes_verified_bytes_and_drops_staging(db_session, store):
    session, org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY

    result = await finalize(session, scan_id, principal, attempt, issued["artifact_id"])

    assert result["verification_state"] == "verified_immutable"
    assert result["storage_uri"].startswith(f"scan-artifacts/{org}/{scan_id}/")
    assert store.objects[result["storage_uri"]] == BODY
    assert issued["key"] not in store.objects
    row = await session.get(ScanArtifact, issued["artifact_id"])
    assert row.checksum_sha256 == sha(BODY)
    assert row.redaction_policy_version


@pytest.mark.asyncio
@pytest.mark.parametrize("problem", ["missing", "wrong_size", "wrong_checksum", "unredacted", "not_json"])
async def test_finalize_rejects_unverifiable_objects_and_publishes_nothing(db_session, store, problem):
    session, _org, _o, scan_id, principal, attempt = await ready(db_session)
    uploaded = {
        "missing": None,
        "wrong_size": BODY + b" ",
        "wrong_checksum": b"x" * len(BODY),
        "unredacted": None,
        "not_json": None,
    }[problem]
    body = BODY
    if problem == "unredacted":
        body = json.dumps({"category": "secret", "match": "AKIA-REAL-KEY"}).encode()
        uploaded = body
    if problem == "not_json":
        body = b"{not json" + b" " * 10
        uploaded = body
    issued = await issue(session, scan_id, principal, attempt, body=body)
    if uploaded is not None:
        store.objects[issued["key"]] = uploaded

    with pytest.raises(HTTPException) as excinfo:
        await finalize(session, scan_id, principal, attempt, issued["artifact_id"], body=body)

    assert excinfo.value.status_code == 422
    assert not [k for k in store.objects if k.startswith("scan-artifacts/")]
    assert issued["key"] not in store.objects  # rejected upload leaves no orphan
    row = await session.get(ScanArtifact, issued["artifact_id"])
    assert row.verification_state == "unavailable"


@pytest.mark.asyncio
async def test_foreign_attempt_or_organization_cannot_finalize(db_session, store):
    session, _org, other_org, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY

    stale = ExecutionAttemptIdentity(str(uuid.uuid4()), attempt.execution_revision, attempt.worker_incarnation_id)
    with pytest.raises(HTTPException) as stale_exc:
        await finalize(session, scan_id, principal, stale, issued["artifact_id"])
    assert stale_exc.value.status_code == 409

    foreign = principal_for(uuid.UUID(other_org))
    with pytest.raises(HTTPException) as foreign_exc:
        await finalize(session, scan_id, foreign, attempt, issued["artifact_id"])
    assert foreign_exc.value.status_code == 403
    assert not [k for k in store.objects if k.startswith("scan-artifacts/")]


@pytest.mark.asyncio
async def test_accepted_objects_cannot_be_overwritten_but_identical_replay_is_idempotent(db_session, store):
    session, _org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY
    first = await finalize(session, scan_id, principal, attempt, issued["artifact_id"])

    replay = await finalize(session, scan_id, principal, attempt, issued["artifact_id"])
    assert replay["storage_uri"] == first["storage_uri"]

    with pytest.raises(HTTPException) as conflict:
        await finalize(session, scan_id, principal, attempt, issued["artifact_id"], body=b'{"other":1}')
    assert conflict.value.status_code == 409

    with pytest.raises(HTTPException) as reissue:
        await issue(session, scan_id, principal, attempt)  # same scanner/filename slot
    assert reissue.value.status_code == 409
    assert store.objects[first["storage_uri"]] == BODY


@pytest.mark.asyncio
async def test_reissued_staging_url_supersedes_the_earlier_one(db_session, store):
    session, _org, _o, scan_id, principal, attempt = await ready(db_session)
    first = await issue(session, scan_id, principal, attempt)
    second = await issue(session, scan_id, principal, attempt)
    store.objects[first["key"]] = BODY

    with pytest.raises(HTTPException) as excinfo:
        await finalize(session, scan_id, principal, attempt, first["artifact_id"])

    assert excinfo.value.status_code == 409
    assert not [k for k in store.objects if k.startswith("scan-artifacts/")]
    assert (await session.get(ScanArtifact, second["artifact_id"])).verification_state == "staged"


@pytest.mark.asyncio
async def test_database_rollback_after_publish_leaves_no_object_or_verified_row(db_session, store, monkeypatch):
    session, _org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY

    real_commit = session.commit

    async def failing_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(session, "commit", failing_commit)
    with pytest.raises(RuntimeError):
        await finalize(session, scan_id, principal, attempt, issued["artifact_id"])
    monkeypatch.setattr(session, "commit", real_commit)

    assert not [k for k in store.objects if k.startswith("scan-artifacts/")]
    row = await session.get(ScanArtifact, issued["artifact_id"])
    assert row.verification_state == "staged"
    assert issued["key"] in store.objects  # still retriable


@pytest.mark.asyncio
async def test_expired_staging_is_swept_and_cannot_be_finalized(db_session, store):
    session, _org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY
    row = await session.get(ScanArtifact, issued["artifact_id"])
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()

    swept = await ArtifactFinalizationService(session, store).expire_stale_staging()

    assert swept == 1
    assert issued["key"] not in store.objects
    assert (await session.get(ScanArtifact, issued["artifact_id"])).verification_state == "expired"
    with pytest.raises(HTTPException) as excinfo:
        await finalize(session, scan_id, principal, attempt, issued["artifact_id"])
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_late_finalize_after_window_is_gone_and_cleans_up(db_session, store):
    session, _org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY
    row = await session.get(ScanArtifact, issued["artifact_id"])
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()

    with pytest.raises(HTTPException) as excinfo:
        await finalize(session, scan_id, principal, attempt, issued["artifact_id"])

    assert excinfo.value.status_code == 410
    assert issued["key"] not in store.objects


@pytest.mark.asyncio
async def test_only_verified_unerased_artifacts_of_the_scan_are_downloadable(db_session, store):
    session, org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY
    done = await finalize(session, scan_id, principal, attempt, issued["artifact_id"])
    service = ArtifactFinalizationService(session, store)

    assert await service.downloadable_uri(scan_id, org, done["storage_uri"]) == done["storage_uri"]
    foreign_key = f"scan-artifacts/{uuid.uuid4()}/{scan_id}/x/trivy/results.json"
    assert await service.downloadable_uri(scan_id, org, foreign_key) is None
    assert await service.downloadable_uri(scan_id, str(uuid.uuid4()), done["storage_uri"]) is None
    staged = await issue(session, scan_id, principal, attempt, filename="other.json")
    planned = (await session.get(ScanArtifact, staged["artifact_id"])).storage_uri
    assert await service.downloadable_uri(scan_id, org, planned) is None

    row = await session.get(ScanArtifact, issued["artifact_id"])
    row.erased_at = datetime.now(UTC)
    await session.commit()
    assert await service.downloadable_uri(scan_id, org, done["storage_uri"]) is None


@pytest.mark.asyncio
async def test_completion_keeps_findings_and_marks_forged_artifacts_unavailable(db_session, store):
    session, org, _o, scan_id, principal, attempt = await ready(db_session)
    issued = await issue(session, scan_id, principal, attempt)
    store.objects[issued["key"]] = BODY
    done = await finalize(session, scan_id, principal, attempt, issued["artifact_id"])

    def run(name, uri, claimed="verified_immutable"):
        return ScannerRunCompletion(
            scanner_name=name,
            status="completed",
            artifact_uri=uri,
            artifact_availability=claimed,
            metadata_json={"raw_output_uri": uri, "keep": "yes"},
        )

    request = ScanCompletionRequest(
        winning_attempt_id=uuid.UUID(attempt.attempt_id),
        execution_revision=attempt.execution_revision,
        worker_incarnation_id=attempt.worker_incarnation_id,
        scanner_runs=[
            run("trivy", done["storage_uri"]),
            run("semgrep", f"scan-artifacts/{uuid.uuid4()}/{scan_id}/z/semgrep/results.json"),
            run("osv", done["storage_uri"]),  # real key, wrong scanner
        ],
    )

    reconciled = await ArtifactFinalizationService(session, store).reconcile_completion_artifacts(
        scan_id, org, request
    )

    trivy, semgrep, osv = reconciled.scanner_runs
    assert (trivy.artifact_uri, trivy.artifact_availability) == (done["storage_uri"], "verified_immutable")
    for forged in (semgrep, osv):
        assert (forged.artifact_uri, forged.artifact_availability) == (None, "unavailable")
        assert forged.metadata_json == {"keep": "yes"}
    assert reconciled.findings == request.findings
