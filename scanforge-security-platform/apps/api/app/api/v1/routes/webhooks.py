from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.webhook import verify_github_webhook_async
from app.db.enums import ScanTriggerType
from app.db.models import Project, Repository, RepositoryIntegration, ScanSchedule, WebhookDelivery
from app.db.session import AsyncSession, get_db
from app.schemas.scans import ScanCreate
from app.services.audit_logs import AuditLogService
from app.services.github_pr_advisory import build_pr_advisory_payload
from app.services.scan_lifecycle import ScanLifecycleService

router = APIRouter()


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

    if (
        not repo
        or not project
        or str(repo.project_id) != str(project_id)
        or str(project.organization_id) != str(org_id)
    ):
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

    db.add(
        WebhookDelivery(
            provider="github",
            delivery_id=delivery,
            event_type=event or "unknown",
            organization_id=str(org_id),
            project_id=str(project_id),
            repository_id=str(repository_id),
        )
    )
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate webhook delivery") from exc

    if event == "push":
        return await _queue_push_scans(
            db=db,
            org_id=org_id,
            repository_id=repository_id,
            payload=payload,
            delivery=delivery,
        )

    if event == "pull_request" and payload.get("action") in {"opened", "reopened", "synchronize"}:
        pull_request = payload.get("pull_request") or {}
        head = pull_request.get("head") or {}
        base = pull_request.get("base") or {}
        if not base.get("sha") or not head.get("sha") or not pull_request.get("number"):
            raise HTTPException(status_code=400, detail="Pull request base, head, and number required")
        try:
            scan_data = ScanCreate(
                repository_id=repository_id,
                trigger_type=ScanTriggerType.PULL_REQUEST,
                branch_name=head.get("ref"),
                commit_sha=head.get("sha"),
                pull_request_number=pull_request.get("number"),
                base_commit_sha=base["sha"],
                head_commit_sha=head["sha"],
                scan_type="diff",
            )
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail="Invalid pull request scan context") from exc

        scan = await ScanLifecycleService(db).create_manual_scan(org_id=org_id, data=scan_data, user_id=None)

        audit_service = AuditLogService(db)
        await audit_service.create(
            actor_user_id=None,
            action="scan_triggered",
            target_type="scan",
            target_id=scan.id,
            organization_id=org_id,
            metadata_json={
                "event": event,
                "delivery": delivery,
                "pull_request_number": pull_request.get("number"),
                "trigger": "github_pull_request_advisory",
            },
        )
        await db.commit()

        return {
            "status": str(scan.status),
            "scan_id": str(scan.id),
            "advisory": build_pr_advisory_payload(
                scan_id=str(scan.id),
                policy_evaluation={"status": "pending", "blocking": False, "reasons": []},
            ),
        }

    if event == "ping":
        await db.commit()
        return {"status": "ok", "message": "Pong"}

    await db.commit()
    return {"status": "ignored", "event": event}


async def _queue_push_scans(*, db: AsyncSession, org_id: UUID, repository_id: UUID, payload: dict, delivery: str):
    ref = payload.get("ref", "")
    if not ref.startswith("refs/heads/") or payload.get("deleted"):
        await db.commit()
        return {"status": "ignored", "event": "push"}
    branch = ref.removeprefix("refs/heads/")
    schedules = await db.scalars(
        select(ScanSchedule)
        .where(
            ScanSchedule.repository_id == str(repository_id),
            ScanSchedule.schedule_type == "on_push",
            ScanSchedule.is_active.is_(True),
        )
        .order_by(ScanSchedule.created_at)
    )
    scan_types = sorted({schedule.scan_type for schedule in schedules.all()})
    if not scan_types:
        await db.commit()
        return {"status": "ignored", "event": "push"}
    scans = []
    lifecycle = ScanLifecycleService(db)
    for scan_type in scan_types:
        scan_data = ScanCreate(
            repository_id=repository_id,
            trigger_type=ScanTriggerType.WEBHOOK,
            branch_name=branch,
            commit_sha=payload.get("after"),
            scan_type=scan_type,
        )
        scan = await lifecycle.create_manual_scan(org_id=org_id, data=scan_data, user_id=None)
        scans.append(scan)
        await AuditLogService(db).create(
            actor_user_id=None,
            action="scan_triggered",
            target_type="scan",
            target_id=scan.id,
            organization_id=org_id,
            metadata_json={"event": "push", "delivery": delivery, "branch": branch, "trigger": "github_push"},
        )
    await db.commit()
    return {"status": str(scans[0].status), "scan_id": str(scans[0].id)}
