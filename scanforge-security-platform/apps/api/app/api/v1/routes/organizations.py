from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.middleware.rbac import require_role
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationSlugPreview,
    OrganizationUpdate,
    OrganizationWithMembers,
)
from app.services.organizations import OrganizationService

router = APIRouter()


@router.get("/slug-preview", response_model=OrganizationSlugPreview)
async def preview_organization_slug(
    slug: str = Query(..., min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    service = OrganizationService(db)
    available_slug = await service.get_available_slug(slug)
    return OrganizationSlugPreview(
        requested_slug=slug,
        available_slug=available_slug,
        adjusted=available_slug != slug,
    )


@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)

    try:
        org, _ = await service.create(data, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return org


@router.get("/", response_model=PaginatedResponse[OrganizationResponse])
async def list_organizations(
    pagination: PaginationParams = Depends(),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    orgs, total = await service.list_for_user(
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        items=orgs,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{org_id}", response_model=OrganizationWithMembers)
async def get_organization(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    org = await service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    data: OrganizationUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)

    has_permission = await service.user_has_permission(
        org_id, current_user.user_id, ["admin", "owner"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can update organizations",
        )

    if data.slug:
        existing = await service.get_by_slug(data.slug)
        if existing and existing.id != org_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization with this slug already exists",
            )

    org = await service.update(org_id, data)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    current_user: UserContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    service = OrganizationService(db)
    deleted = await service.delete(org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Organization not found")
