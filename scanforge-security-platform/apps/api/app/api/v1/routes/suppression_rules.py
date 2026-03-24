from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.policy import SuppressionRule
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.services.organizations import OrganizationService

router = APIRouter()


class SuppressionRuleCreate(BaseModel):
    rule_type: str
    match_criteria_json: dict
    reason: str
    project_id: UUID | None = None
    repository_id: UUID | None = None
    expires_at: str | None = None


class SuppressionRuleUpdate(BaseModel):
    is_active: bool | None = None
    reason: str | None = None


@router.post("/organizations/{org_id}/suppression-rules", status_code=201)
async def create_rule(
    org_id: UUID,
    body: SuppressionRuleCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create suppression rules",
        )

    rule = SuppressionRule(
        organization_id=str(org_id),
        project_id=str(body.project_id) if body.project_id else None,
        repository_id=str(body.repository_id) if body.repository_id else None,
        rule_type=body.rule_type,
        match_criteria_json=body.match_criteria_json,
        reason=body.reason,
        is_active=True,
        created_by_user_id=str(current_user.user_id),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/organizations/{org_id}/suppression-rules")
async def list_rules(
    org_id: UUID,
    skip: int = 0,
    limit: int = 50,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    is_member = await org_service.is_member(org_id, current_user.user_id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    total = (
        await db.execute(
            select(func.count()).select_from(SuppressionRule).where(SuppressionRule.organization_id == str(org_id))
        )
    ).scalar_one()
    result = await db.execute(
        select(SuppressionRule)
        .where(SuppressionRule.organization_id == str(org_id))
        .order_by(SuppressionRule.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rules = result.scalars().all()
    return {"items": rules, "total": total, "skip": skip, "limit": limit}


@router.patch("/organizations/{org_id}/suppression-rules/{rule_id}")
async def update_rule(
    org_id: UUID,
    rule_id: UUID,
    body: SuppressionRuleUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update suppression rules",
        )

    result = await db.execute(
        select(SuppressionRule).where(SuppressionRule.id == rule_id, SuppressionRule.organization_id == str(org_id))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if body.is_active is not None:
        rule.is_active = body.is_active
    if body.reason is not None:
        rule.reason = body.reason
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/organizations/{org_id}/suppression-rules/{rule_id}", status_code=204)
async def delete_rule(
    org_id: UUID,
    rule_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["owner", "admin"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can delete suppression rules",
        )

    result = await db.execute(
        select(SuppressionRule).where(SuppressionRule.id == rule_id, SuppressionRule.organization_id == str(org_id))
    )
    rule = result.scalar_one_or_none()
    if rule:
        await db.delete(rule)
        await db.commit()
