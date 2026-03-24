from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.core.config import settings
from app.core.webhook import verify_github_webhook_async
from app.db.enums import ScanTriggerType
from app.db.session import AsyncSession, get_db
from app.schemas.scans import ScanCreate
from app.services.audit_logs import AuditLogService
from app.services.scans import ScanService

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

    payload = await request.json()

    if event == "push":
        branch = payload.get("ref", "").replace("refs/heads/", "")

        scan_service = ScanService(db)
        scan_data = ScanCreate(
            repository_id=repository_id,
            trigger_type=ScanTriggerType.WEBHOOK,
            branch_name=branch,
            commit_sha=payload.get("after"),
        )

        scan, _, _ = await scan_service.create(
            str(repository_id), scan_data, user_id=None
        )

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
                "branch": branch,
                "trigger": "github_push",
            },
        )

        return {"status": "queued", "scan_id": str(scan.id)}

    if event == "ping":
        return {"status": "ok", "message": "Pong"}

    return {"status": "ignored", "event": event}


