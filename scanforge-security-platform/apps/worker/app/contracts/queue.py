from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ScanJobType = Literal["scan.repo.full", "scan.repo.diff", "scan.dependencies", "scan.secrets"]
SCAN_JOB_TYPES: tuple[str, ...] = ("scan.repo.full", "scan.repo.diff", "scan.dependencies", "scan.secrets")


class QueueJob(BaseModel):
    job_type: str
    job_id: str
    payload: dict = Field(default_factory=dict)
    created_at: str
    stream_id: str | None = Field(default=None, exclude=True)

    @field_validator("payload")
    @classmethod
    def validate_scan_payload(cls, payload: dict) -> dict:
        scan_id = payload.get("scan_id")
        if not isinstance(scan_id, str) or not scan_id:
            raise ValueError("scan job payload requires scan_id")
        return payload

    @classmethod
    def create(cls, job_type: ScanJobType, payload: dict) -> "QueueJob":
        scan_id = payload.get("scan_id")
        if not isinstance(scan_id, str) or not scan_id:
            return cls(
                job_type=job_type,
                job_id="",
                payload=payload,
                created_at=datetime.now(UTC).isoformat(),
            )
        return cls(
            job_type=job_type,
            job_id=scan_id,
            payload=payload,
            created_at=datetime.now(UTC).isoformat(),
        )
