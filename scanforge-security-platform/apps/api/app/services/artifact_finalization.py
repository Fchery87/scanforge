"""Immutable verified artifact finalization (redirection plan P1.7, issue #43).

Workers upload sanitized scanner output to an attempt-scoped *staging* key
through a short-lived presigned URL.  Nothing there is trusted.  The API
publishes an object under the immutable ``scan-artifacts/`` prefix only after
it has verified organization, scan, attempt and scanner ownership, existence,
size, SHA-256 and the redaction policy.  The bytes that were hashed are the
bytes that are published, and a published key is never written twice.

A ``scan_artifacts`` row is the only reference to a published object.
Downloads and scanner-run references resolve through verified rows, so an
object without a verified row is never exposed.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from sqlalchemy import select

from app.db.enums import ArtifactVerificationState
from app.db.models import ScanArtifact
from app.services.secret_safety import sanitize_secret_mapping

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.scan_completion import ScanCompletionRequest

STAGING_PREFIX = "scan-staging"
PUBLISHED_PREFIX = "scan-artifacts"
REDACTION_POLICY_VERSION = "redaction.v1"
PRESIGN_SECONDS = 300
# Issued URLs cannot be revoked, so staged rows (and the URLs issued for them)
# are bounded: after this window nothing can still be written for the row.
STAGING_TTL = timedelta(minutes=15)
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
JSON_CONTENT_TYPES = frozenset(
    {"application/json", "application/sarif+json", "application/vnd.cyclonedx+json"}
)
_STAGED = ArtifactVerificationState.STAGED.value
_VERIFIED = ArtifactVerificationState.VERIFIED_IMMUTABLE.value
_UNAVAILABLE = ArtifactVerificationState.UNAVAILABLE.value
_EXPIRED = ArtifactVerificationState.EXPIRED.value


class ArtifactStore(Protocol):
    def generate_presigned_upload_url(self, key: str, content_type: str, expires_in: int = ...) -> str: ...
    def object_size(self, key: str) -> int | None: ...
    def read_object(self, key: str, max_bytes: int) -> bytes: ...
    def put_object_if_absent(self, key: str, body: bytes, content_type: str) -> None: ...
    def delete_object(self, key: str) -> None: ...


class ArtifactFinalizationError(Exception):
    status_code = 422
    code = "artifact_rejected"


class ArtifactNotFound(ArtifactFinalizationError):
    status_code = 404
    code = "artifact_not_found"


class ArtifactConflict(ArtifactFinalizationError):
    status_code = 409
    code = "artifact_conflict"


class ArtifactExpired(ArtifactFinalizationError):
    status_code = 410
    code = "artifact_staging_expired"


def valid_component(value: str) -> bool:
    return (
        bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and "\x00" not in value
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _snapshot(artifact: ScanArtifact) -> dict[str, object]:
    return {
        "artifact_id": artifact.id,
        "storage_uri": artifact.storage_uri,
        "size_bytes": artifact.size_bytes,
        "checksum_sha256": artifact.checksum_sha256,
        "verification_state": artifact.verification_state,
    }


def _filename(artifact: ScanArtifact) -> str:
    return artifact.storage_uri.rsplit("/", 1)[-1]


class ArtifactFinalizationService:
    def __init__(self, db: AsyncSession, store: ArtifactStore):
        self.db = db
        self.store = store

    # -- staging ---------------------------------------------------------

    async def stage(
        self,
        *,
        organization_id: str,
        scan_id: str,
        attempt_id: str,
        scanner_name: str,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> dict[str, str]:
        """Record an expected upload; return its id, staging key and presigned URL."""
        organization_id, scan_id, attempt_id = str(organization_id), str(scan_id), str(attempt_id)
        rows = await self._rows_for_slot(scan_id, attempt_id, scanner_name, filename)
        if any(row.verification_state == _VERIFIED for row in rows):
            raise ArtifactConflict("An accepted artifact already exists for this scanner output")
        for row in rows:
            if row.verification_state == _STAGED:
                row.verification_state = _UNAVAILABLE

        artifact_id = str(uuid4())
        staging_key = (
            f"{STAGING_PREFIX}/{organization_id}/{scan_id}/{attempt_id}/"
            f"{artifact_id}/{scanner_name}/{filename}"
        )
        artifact = ScanArtifact(
            id=artifact_id,
            scan_id=scan_id,
            organization_id=organization_id,
            attempt_id=attempt_id,
            scanner_name=scanner_name,
            artifact_type="scanner_output",
            staging_uri=staging_key,
            storage_uri=(
                f"{PUBLISHED_PREFIX}/{organization_id}/{scan_id}/{artifact_id}/{scanner_name}/{filename}"
            ),
            verification_state=_STAGED,
            content_type=content_type,
            size_bytes=size_bytes,
            expires_at=datetime.now(UTC) + STAGING_TTL,
        )
        self.db.add(artifact)
        await self.db.flush()
        upload_url = self.store.generate_presigned_upload_url(staging_key, content_type, PRESIGN_SECONDS)
        await self.db.commit()
        return {"artifact_id": artifact_id, "key": staging_key, "upload_url": upload_url}

    async def _rows_for_slot(
        self, scan_id: str, attempt_id: str, scanner_name: str, filename: str
    ) -> list[ScanArtifact]:
        result = await self.db.execute(
            select(ScanArtifact).where(
                ScanArtifact.scan_id == scan_id,
                ScanArtifact.attempt_id == attempt_id,
                ScanArtifact.scanner_name == scanner_name,
            )
        )
        return [row for row in result.scalars() if _filename(row) == filename]

    # -- finalization ----------------------------------------------------

    async def finalize(
        self,
        *,
        organization_id: str,
        scan_id: str,
        attempt_id: str,
        artifact_id: str,
        checksum_sha256: str,
    ) -> dict[str, object]:
        artifact = await self.db.get(ScanArtifact, str(artifact_id))
        if (
            artifact is None
            or artifact.organization_id != str(organization_id)
            or artifact.scan_id != str(scan_id)
            or artifact.attempt_id != str(attempt_id)
        ):
            raise ArtifactNotFound("Artifact not found for this scan attempt")

        checksum = checksum_sha256.lower()
        if artifact.verification_state == _VERIFIED:
            if artifact.checksum_sha256 == checksum:
                return _snapshot(artifact)  # identical replay
            raise ArtifactConflict("Accepted artifacts cannot be overwritten")
        if artifact.verification_state != _STAGED:
            raise ArtifactConflict("Artifact is no longer awaiting finalization")
        expires_at = _aware(artifact.expires_at)
        if expires_at is not None and expires_at < datetime.now(UTC):
            await self._discard(artifact, _EXPIRED)
            raise ArtifactExpired("Artifact staging window has expired")

        siblings = await self._rows_for_slot(
            artifact.scan_id, artifact.attempt_id, artifact.scanner_name, _filename(artifact)
        )
        if any(row.id != artifact.id and row.verification_state == _VERIFIED for row in siblings):
            raise ArtifactConflict("An accepted artifact already exists for this scanner output")

        try:
            body = self._read_verified_bytes(artifact, checksum)
        except ArtifactFinalizationError:
            await self._discard(artifact, _UNAVAILABLE)
            raise

        published_key = artifact.storage_uri
        try:
            self.store.put_object_if_absent(published_key, body, artifact.content_type or "application/json")
        except FileExistsError as exc:
            raise ArtifactConflict("Accepted artifacts cannot be overwritten") from exc
        staging_key = artifact.staging_uri
        artifact.verification_state = _VERIFIED
        artifact.checksum_sha256 = checksum
        artifact.redaction_policy_version = REDACTION_POLICY_VERSION
        artifact.verified_at = datetime.now(UTC)
        artifact.expires_at = None
        artifact.staging_uri = None
        snapshot = _snapshot(artifact)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            self._delete_quietly(published_key)
            raise
        if staging_key:
            self._delete_quietly(staging_key)
        return snapshot

    def _read_verified_bytes(self, artifact: ScanArtifact, checksum: str) -> bytes:
        staging_key = artifact.staging_uri
        size = self.store.object_size(staging_key) if staging_key else None
        if size is None:
            raise ArtifactFinalizationError("Staged object does not exist")
        declared = artifact.size_bytes
        if declared is None or size != declared or size > MAX_ARTIFACT_BYTES:
            raise ArtifactFinalizationError("Staged object size does not match the declared size")
        body = self.store.read_object(staging_key, declared)
        if len(body) != declared:
            raise ArtifactFinalizationError("Staged object size does not match the declared size")
        if hashlib.sha256(body).hexdigest() != checksum:
            raise ArtifactFinalizationError("Staged object checksum does not match")
        self._enforce_redaction_policy(artifact, body)
        return body

    @staticmethod
    def _enforce_redaction_policy(artifact: ScanArtifact, body: bytes) -> None:
        if artifact.content_type not in JSON_CONTENT_TYPES:
            raise ArtifactFinalizationError("Redaction cannot be verified for this content type")
        try:
            parsed = json.loads(body)
        except ValueError as exc:
            raise ArtifactFinalizationError("Artifact is not valid JSON") from exc
        if sanitize_secret_mapping(parsed) != parsed:
            raise ArtifactFinalizationError("Artifact contains secret material that policy requires redacted")

    async def _discard(self, artifact: ScanArtifact, state: str) -> None:
        staging_key = artifact.staging_uri
        artifact.verification_state = state
        artifact.staging_uri = None
        await self.db.commit()
        if staging_key:
            self._delete_quietly(staging_key)

    def _delete_quietly(self, key: str) -> None:
        # Best effort: the expiry sweep retries anything left behind.
        with contextlib.suppress(Exception):
            self.store.delete_object(key)

    # -- expiry / orphan cleanup -----------------------------------------

    async def expire_stale_staging(self, now: datetime | None = None) -> int:
        """Delete staged objects whose window passed and mark their rows expired."""
        now = now or datetime.now(UTC)
        result = await self.db.execute(
            select(ScanArtifact).where(
                ScanArtifact.verification_state.in_([_STAGED, _UNAVAILABLE]),
                ScanArtifact.staging_uri.is_not(None),
            )
        )
        swept = 0
        for artifact in result.scalars():
            expires_at = _aware(artifact.expires_at)
            if expires_at is None or expires_at >= now:
                continue
            staging_key, artifact.staging_uri = artifact.staging_uri, None
            if artifact.verification_state == _STAGED:
                artifact.verification_state = _EXPIRED
            self._delete_quietly(staging_key)
            swept += 1
        await self.db.commit()
        return swept

    # -- references ------------------------------------------------------

    async def downloadable_uri(self, scan_id: str, organization_id: str, storage_uri: str | None) -> str | None:
        """Return ``storage_uri`` only when a live verified artifact of this scan owns it."""
        if not storage_uri:
            return None
        row = (
            (
                await self.db.execute(
                    select(ScanArtifact).where(
                        ScanArtifact.storage_uri == storage_uri,
                        ScanArtifact.scan_id == str(scan_id),
                        ScanArtifact.organization_id == str(organization_id),
                        ScanArtifact.verification_state == _VERIFIED,
                    )
                )
            )
            .scalars()
            .first()
        )
        if row is None or row.erased_at is not None:
            return None
        expires_at = _aware(row.expires_at)
        if expires_at is not None and expires_at < datetime.now(UTC):
            return None
        return row.storage_uri

    async def reconcile_completion_artifacts(
        self, scan_id: str, organization_id: str, data: ScanCompletionRequest
    ) -> ScanCompletionRequest:
        """Replace worker-claimed artifact references with verified ones.

        A reference survives only when it names a verified artifact of this
        scan, scanner and winning attempt.  Anything else is dropped and the
        run's secondary artifacts are marked unavailable; findings are untouched.
        """
        if not any(_claims_artifact(run) for run in data.scanner_runs):
            return data
        result = await self.db.execute(
            select(ScanArtifact).where(
                ScanArtifact.scan_id == str(scan_id),
                ScanArtifact.organization_id == str(organization_id),
                ScanArtifact.attempt_id == str(data.winning_attempt_id),
                ScanArtifact.verification_state == _VERIFIED,
            )
        )
        verified = {
            (row.scanner_name, row.storage_uri) for row in result.scalars() if row.erased_at is None
        }
        runs = []
        for run in data.scanner_runs:
            uri = run.artifact_uri if (run.scanner_name, run.artifact_uri) in verified else None
            metadata = run.metadata_json
            if isinstance(metadata, dict):
                metadata = {
                    key: value
                    for key, value in metadata.items()
                    if not (key.endswith("_uri") and (run.scanner_name, value) not in verified)
                }
            runs.append(
                run.model_copy(
                    update={
                        "artifact_uri": uri,
                        "artifact_availability": "verified_immutable" if uri else "unavailable",
                        "metadata_json": metadata,
                    }
                )
            )
        return data.model_copy(update={"scanner_runs": runs})


def _claims_artifact(run) -> bool:
    metadata = run.metadata_json
    return bool(
        run.artifact_uri
        or run.artifact_availability != "unavailable"
        or (isinstance(metadata, dict) and any(key.endswith("_uri") for key in metadata))
    )
