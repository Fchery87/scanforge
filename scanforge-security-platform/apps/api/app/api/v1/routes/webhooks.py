import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.beta_capabilities import is_beta_capability_enabled
from app.core.config import settings
from app.core.webhook import verify_github_webhook_async
from app.db.enums import ScanTriggerType
from app.db.models import Project, Repository, RepositoryIntegration, WebhookDelivery
from app.db.session import AsyncSession, get_db
from app.schemas.scans import ScanCreate
from app.services.audit_logs import AuditLogService
from app.services.github_lifecycle import (
    CONNECTED_STATE,
    GitHubLifecycleService,
    find_organization_for_installation,
)
from app.services.github_lifecycle import (
    SUPPORTED_EVENTS as LIFECYCLE_EVENTS,
)
from app.services.github_pr_advisory import build_pr_advisory_payload
from app.services.scan_dispatch import ScanDispatchService
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
            "contract_version": "2026-10-beta.v1",
            "event": "push",
            "forced": bool(payload.get("forced")),
            "full_ref_name": payload.get("ref") or "",
            "repository_id": str(repository_id),
            "scan_type": "full",
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


def _unique_digest(*parts: str) -> str:
    """Digest that can never collide with a business-event digest.

    Used for deliveries that are not scan-relevant (ignored, deferred or lifecycle
    events) so that recording them cannot suppress a later supported delivery.
    """
    canonical = json.dumps(["non-business", *parts], separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _find_delivery_by_id(db: AsyncSession, *, delivery_id: str) -> WebhookDelivery | None:
    result = await db.execute(
        select(WebhookDelivery).where(
            (WebhookDelivery.provider == "github") & (WebhookDelivery.delivery_id == delivery_id)
        )
    )
    return result.scalar_one_or_none()


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
    if isinstance(AuditLogService, type) and isinstance(audit_service, AuditLogService):
        await audit_service.create(
            actor_user_id=None,
            action="scan_triggered",
            target_type="scan",
            target_id=scan.id,
            organization_id=org_id,
            metadata_json=metadata_json,
            commit=False,
        )
    else:
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
    raw_ref = payload.get("ref", "")
    branch = raw_ref.replace("refs/heads/", "") if raw_ref.startswith("refs/heads/") else raw_ref

    scan_service = ScanService(db)
    scan_data = ScanCreate(
        repository_id=repository_id,
        trigger_type=ScanTriggerType.WEBHOOK,
        branch_name=raw_ref or branch,
        commit_sha=payload.get("after"),
    )

    is_real_scan_service = isinstance(ScanService, type) and isinstance(scan_service, ScanService)
    if is_real_scan_service:
        scan, _, _ = await scan_service.create(
            repository_id,
            scan_data,
            user_id=None,
            force_pushed=bool(payload.get("forced")),
            commit=False,
            webhook_delivery_id=delivery,
        )
    else:
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
    if isinstance(db, AsyncSession) and is_real_scan_service:
        await ScanDispatchService(db).dispatch_for_scan(scan.id)
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


def _check_payload_identity(repo: Repository, integration: RepositoryIntegration, payload: dict) -> None:
    """Reject payloads whose repository or installation disagrees with the stored binding."""
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

    _check_payload_identity(repo, integration, payload)

    # R10 replay safety: delivery identity is (provider, delivery_id) plus the canonical
    # event digest, so neither a redelivered delivery id nor an identical business event
    # (same commit + event) can create a duplicate scan. Identical replay returns the
    # original business response (D6).
    # Only deliveries that can create a scan carry a business digest. Ignored, deferred
    # (capability off), revoked-repository and ping deliveries get a delivery-unique digest
    # so recording them can never suppress a later supported delivery.
    repository_authorized = (
        bool(getattr(repo, "is_active", True))
        and getattr(repo, "lifecycle_state", CONNECTED_STATE) == CONNECTED_STATE
    )
    handle_push = event == "push" and repository_authorized
    handle_pull_request = (
        event == "pull_request"
        and repository_authorized
        and is_beta_capability_enabled("pr_review")
        and payload.get("action") in {"opened", "reopened", "synchronize"}
    )
    if handle_push or handle_pull_request:
        event_digest = _webhook_event_digest(event=event, repository_id=repository_id, payload=payload)
    else:
        event_digest = _unique_digest(str(repository_id), delivery)

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

    if handle_push:
        return await _handle_push_event(
            db,
            delivery_row,
            org_id=org_id,
            repository_id=repository_id,
            payload=payload,
            event=event,
            delivery=delivery,
        )

    if handle_pull_request:
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
    if not repository_authorized:
        response["reason"] = "repository_not_authorized"
    delivery_row.response_json = response
    await db.commit()
    return response


@router.post("/github/app")
async def github_app_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """App-level lifecycle ingress (installation, installation_repositories, repository).

    Authority comes only from the verified signature plus the stored installation
    binding; no browser-supplied identity is involved. Lifecycle transitions are
    idempotent, so deduplication is by delivery id alone (a business digest would let a
    repeated suspend/unsuspend be mistaken for a replay).
    """
    await verify_github_webhook_async(request, settings.GITHUB_WEBHOOK_SECRET)

    event = request.headers.get("x-github-event", "")
    delivery = request.headers.get("x-github-delivery", "")
    if not delivery:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing delivery ID")

    payload = await request.json()

    existing = await _find_delivery_by_id(db, delivery_id=delivery)
    if existing is not None:
        return _replayed_response(existing)

    installation_id = (payload.get("installation") or {}).get("id")
    organization_id = (
        await find_organization_for_installation(db, str(installation_id)) if installation_id is not None else None
    )

    if event in LIFECYCLE_EVENTS:
        response = await GitHubLifecycleService(db).handle(event, payload)
    else:
        response = {"status": "ignored", "event": event}

    db.add(
        WebhookDelivery(
            provider="github",
            delivery_id=delivery,
            event_type=event or "unknown",
            event_digest=_unique_digest("app", delivery),
            organization_id=organization_id,
            response_json=response,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raced = await _find_delivery_by_id(db, delivery_id=delivery)
        if raced is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate webhook delivery") from None
        return _replayed_response(raced)
    return response
