from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.route_auth import get_project_in_org_or_404
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.audit_logs import AuditLogService
from app.services.organizations import OrganizationService

router = APIRouter()


@router.get("/organizations/{org_id}/audit-logs", response_model=PaginatedResponse[dict])
async def list_audit_logs_org(
    org_id: UUID,
    pagination: PaginationParams = Depends(),
    action: str | None = Query(None, alias="action"),
    actor_user_id: UUID | None = Query(None, alias="actorUserId"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer"]
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Not authorized to view audit logs")

    service = AuditLogService(db)
    logs, total = await service.list_for_organization(
        org_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        action=action,
        actor_user_id=actor_user_id,
    )

    return PaginatedResponse(
        items=logs,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get(
    "/organizations/{org_id}/projects/{project_id}/audit-logs",
    response_model=PaginatedResponse[dict],
)
async def list_audit_logs_project(
    org_id: UUID,
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    action: str | None = Query(None, alias="action"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    service = AuditLogService(db)
    logs, total = await service.list_for_project(
        project_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        action=action,
    )

    return PaginatedResponse(
        items=logs,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )
