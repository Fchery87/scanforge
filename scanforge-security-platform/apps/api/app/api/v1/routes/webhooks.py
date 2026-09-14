import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.webhook import verify_github_webhook_async
from app.db.enums import ScanTriggerType
from app.db.models import Project, Repository, RepositoryIntegration, WebhookDelivery
from app.db.session import AsyncSession, get_db
from app.schemas.scans import ScanCreate
from app.services.audit_logs import AuditLogService
from app.services.github_pr_advisory import build_pr_advisory_payload
from app.services.scan_lifecycle import ScanLifecycleService
from app.services.scans import ScanService

router = APIRouter()


def _webhook_event_digest(*, event: str, repository_id: UUID, payload: dict) -> str:
    """Canonical digest of the scan-relevant event identity.

    Follows the D6 replay convention (spec/2026-09-13-scan-evidence-decisions.md):
    canonical JSON (sorted keys, compact separators) of the business content,
    hashed with SHA-256. Two deliveries carrying identical business content
    (same commit + event + repository) produce the same digest, so a redelivery
    under a different GitHub delivery id still maps to the original scan.
    """
    if event == "push":
        identity = {
            "branch": (payload.get("ref") or "").replace("refs/heads/", ""),
            "commit": payload.get("after"),
            "event": "push",
            "repository_id": str(repository_id),
        }
    elif event == "pull_request":
        pull_request = payload.get("pull_request") or {}
        identity = {
            "base_sha": (pull_request.get("base") or {}).get("sha"),
            "event": "pull_request",
            "head_sha": (pull_request.get("head") or {}).get("sha"),
            "pull_request_number": pull_request.get("number"),
            "repository_id": str(repository_id),
        }
    else:
        identity = {"event": event or "unknown", "repository_id": str(repository_id)}

    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _find_existing_delivery(
    db: AsyncSession, *, delivery_id: str, event_digest: str
) -> WebhookDelivery | None:
    result = await db.execute(
        select(WebhookDelivery).where(
            (WebhookDelivery.provider == "github")
            & (
                (WebhookDelivery.delivery_id == delivery_id)
                | (WebhookDelivery.event_digest == event_digest)
            )
        )
    )
    return result.scalar_one_or_none()


def _replayed_response(delivery: WebhookDelivery) -> dict:
    """Original business response for an identical replay (D6)."""
    if delivery.response_json:
        return dict(delivery.response_json)
    if delivery.scan_id:
        return {"status": "queued", "scan_id": str(delivery.scan_id)}
    if delivery.event_type == "ping":
        return {"status": "ok", "message": "Pong"}
    return {"status": "ignored", "event": delivery.event_type}


async def _record_scan_delivery(
    audit_service: AuditLogService,
    delivery_row: WebhookDelivery,
    *,
    scan,
    org_id: UUID,
    event: str,
    delivery: str,
    metadata_json: dict,
    response: dict,
) -> dict:
    await audit_service.create(
        actor_user_id=None,
        action="scan_triggered",
        target_type="scan",
        target_id=scan.id,
        organization_id=org_id,
        metadata_json=metadata_json,
    )
    delivery_row.scan_id = scan.id
    delivery_row.response_json = response
    return response


async def _handle_push_event(
    db: AsyncSession,
    delivery_row: WebhookDelivery,
    *,
    org_id: UUID,
    repository_id: UUID,
    payload: dict,
    event: str,
    delivery: str,
) -> dict:
    branch = payload.get("ref", "").replace("refs/heads/", "")

    scan_service = ScanService(db)
    scan_data = ScanCreate(
        repository_id=repository_id,
        trigger_type=ScanTriggerType.WEBHOOK,
        branch_name=branch,
        commit_sha=payload.get("after"),
    )

    scan, _, _ = await scan_service.create(repository_id, scan_data, user_id=None)

    response = await _record_scan_delivery(
        AuditLogService(db),
        delivery_row,
        scan=scan,
        org_id=org_id,
        event=event,
        delivery=delivery,
        metadata_json={
            "event": event,
            "delivery": delivery,
            "branch": branch,
            "trigger": "github_push",
        },
        response={"status": "queued", "scan_id": str(scan.id)},
    )
    await db.commit()
    return response


async def _handle_pull_request_event(
    db: AsyncSession,
    delivery_row: WebhookDelivery,
    *,
    org_id: UUID,
    repository_id: UUID,
    payload: dict,
    event: str,
    delivery: str,
) -> dict:
    pull_request = payload.get("pull_request") or {}
    head = pull_request.get("head") or {}
    base = pull_request.get("base") or {}
    scan_data = ScanCreate(
        repository_id=repository_id,
        trigger_type=ScanTriggerType.PULL_REQUEST,
        branch_name=head.get("ref"),
        commit_sha=head.get("sha"),
        # R10 recorded base/head diff: the pull_request event carries both sides.
        base_sha=base.get("sha"),
        pull_request_number=pull_request.get("number"),
        scan_type="diff",
    )

    scan = await ScanLifecycleService(db).create_manual_scan(org_id=org_id, data=scan_data, user_id=None)

    response = await _record_scan_delivery(
        AuditLogService(db),
        delivery_row,
        scan=scan,
        org_id=org_id,
        event=event,
        delivery=delivery,
        metadata_json={
            "event": event,
            "delivery": delivery,
            "pull_request_number": pull_request.get("number"),
            "trigger": "github_pull_request_advisory",
        },
        response={
            "status": "queued",
            "scan_id": str(scan.id),
            "advisory": build_pr_advisory_payload(
                scan_id=str(scan.id),
                policy_evaluation={"status": "pass", "blocking": False, "reasons": []},
            ),
        },
    )
    await db.commit()
    return response


@router.post("/github/{org_id}/{project_id}/{repository_id}")
async def github_webhook(
    org_id: UUID,
    project_id: UUID,
    repository_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await verify_github_webhook_async(request, settings.GITHUB_WEBHOOK_SECRET)

    event = request.headers.get("x-github-event", "")
    delivery = request.headers.get("x-github-delivery", "")
    if not delivery:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing delivery ID")

    payload = await request.json()

    repo = await db.get(Repository, repository_id)
    project = await db.get(Project, project_id)
    integration = await db.scalar(
        select(RepositoryIntegration).where(RepositoryIntegration.repository_id == repository_id)
    )

    if not repo or not project or repo.project_id != project_id or project.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook target not found")

    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository integration not found")

    payload_repo = payload.get("repository") or {}
    payload_installation = payload.get("installation") or {}
    payload_full_name = payload_repo.get("full_name")
    payload_repo_id = str(payload_repo.get("id")) if payload_repo.get("id") is not None else None
    payload_installation_id = (
        str(payload_installation.get("id")) if payload_installation.get("id") is not None else None
    )

    if payload_full_name != repo.full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook repository mismatch")

    if repo.external_repo_id and payload_repo_id and repo.external_repo_id != payload_repo_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook repository ID mismatch")

    if integration.installation_id and payload_installation_id != integration.installation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook installation mismatch")

    # R10 replay safety: delivery identity is (provider, delivery_id) plus the canonical
    # event digest, so neither a redelivered delivery id nor an identical business event
    # (same commit + event) can create a duplicate scan. Identical replay returns the
    # original business response (D6).
    event_digest = _webhook_event_digest(event=event, repository_id=repository_id, payload=payload)

    existing = await _find_existing_delivery(db, delivery_id=delivery, event_digest=event_digest)
    if existing is not None:
        return _replayed_response(existing)

    delivery_row = WebhookDelivery(
        provider="github",
        delivery_id=delivery,
        event_type=event or "unknown",
        event_digest=event_digest,
        organization_id=str(org_id),
        project_id=str(project_id),
        repository_id=str(repository_id),
    )
    db.add(delivery_row)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Concurrent redelivery raced past the pre-check: roll back and replay the
        # winning row; only an unknown conflict stays a hard 409.
        await db.rollback()
        raced = await _find_existing_delivery(db, delivery_id=delivery, event_digest=event_digest)
        if raced is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate webhook delivery") from exc
        return _replayed_response(raced)

    if event == "push":
        return await _handle_push_event(
            db,
            delivery_row,
            org_id=org_id,
            repository_id=repository_id,
            payload=payload,
            event=event,
            delivery=delivery,
        )

    if event == "pull_request" and payload.get("action") in {"opened", "reopened", "synchronize"}:
        return await _handle_pull_request_event(
            db,
            delivery_row,
            org_id=org_id,
            repository_id=repository_id,
            payload=payload,
            event=event,
            delivery=delivery,
        )

    if event == "ping":
        delivery_row.response_json = {"status": "ok", "message": "Pong"}
        await db.commit()
        return {"status": "ok", "message": "Pong"}

    response = {"status": "ignored", "event": event}
    delivery_row.response_json = response
    await db.commit()
    return response
