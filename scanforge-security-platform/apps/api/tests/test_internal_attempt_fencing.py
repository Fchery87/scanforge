from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes.internal import ExecutionAttemptIdentity, assert_live_execution_authority
from app.middleware.service_auth import WorkerPrincipal


def _authority():
    worker_id = uuid4()
    attempt_id = str(uuid4())
    incarnation_id = str(uuid4())
    principal = WorkerPrincipal(worker_id=worker_id, organization_id=uuid4(), capabilities=frozenset())
    scan = SimpleNamespace(
        current_attempt_id=attempt_id,
        execution_revision=3,
        worker_incarnation_id=incarnation_id,
        lease_owner=str(worker_id),
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    return scan, principal, ExecutionAttemptIdentity(
        attempt_id=attempt_id,
        execution_revision=3,
        worker_incarnation_id=incarnation_id,
    )


def test_live_attempt_owner_can_mutate_current_scan():
    scan, principal, attempt = _authority()

    assert_live_execution_authority(scan, principal, attempt)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("current_attempt_id", str(uuid4()), "stale_attempt"),
        ("execution_revision", 4, "stale_attempt"),
        ("worker_incarnation_id", str(uuid4()), "stale_attempt"),
        ("lease_owner", str(uuid4()), "stale_worker"),
        ("lease_expires_at", datetime.now(UTC) - timedelta(seconds=1), "lease_expired"),
        ("lease_expires_at", None, "lease_missing"),
    ],
)
def test_replaced_owner_attempt_or_expired_lease_cannot_mutate(field, value, expected_code):
    scan, principal, attempt = _authority()
    setattr(scan, field, value)

    with pytest.raises(HTTPException) as error:
        assert_live_execution_authority(scan, principal, attempt)

    assert error.value.status_code == 409
    assert error.value.detail["code"] == expected_code
