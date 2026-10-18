import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import MemberRole
from app.db.models import OrganizationInvitation, OrganizationMember, User
from app.schemas.memberships import MemberInvite
from app.services.audit_logs import AuditLogService

INVITATION_TTL_DAYS = 7


class MembershipAuthorizationError(PermissionError):
    """Caller is not authorized to perform this membership operation."""


def _hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class MembershipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_active_actor_member(
        self,
        org_id: UUID,
        actor_user_id: UUID,
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(actor_user_id),
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def _require_role_management_authority(
        self,
        org_id: UUID,
        actor_user_id: UUID,
        *,
        target_role: str,
    ) -> OrganizationMember:
        actor = await self._get_active_actor_member(org_id, actor_user_id)
        if actor is None or actor.role not in ("owner", "admin"):
            raise MembershipAuthorizationError("Only owners and admins can manage organization memberships")
        if target_role == "owner":
            raise MembershipAuthorizationError("Use ownership transfer to assign owner role")
        if target_role == "admin" and actor.role != "owner":
            raise MembershipAuthorizationError("Only owners can appoint or remove admins")
        return actor

    async def add_member(
        self,
        org_id: UUID,
        user_id: UUID,
        role: str,
        *,
        actor_user_id: UUID | None = None,
        commit: bool = True,
    ) -> OrganizationMember:
        if actor_user_id is not None:
            await self._require_role_management_authority(
                org_id,
                actor_user_id,
                target_role=role,
            )

        existing = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("User is already a member")

        member = OrganizationMember(
            organization_id=str(org_id),
            user_id=str(user_id),
            role=role,
        )
        self.db.add(member)
        await self.db.flush()
        AuditLogService(self.db).record(
            actor_user_id=actor_user_id or user_id,
            action="member_added",
            target_type="membership",
            target_id=member.id,
            organization_id=org_id,
            metadata_json={"user_id": str(user_id), "role": str(role)},
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(member)
        return member

    async def remove_member(
        self,
        org_id: UUID,
        user_id: UUID,
        *,
        actor_user_id: UUID | None = None,
        commit: bool = True,
    ) -> bool:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False

        if member.role == "owner":
            raise ValueError("Cannot remove the owner")

        if actor_user_id is not None:
            await self._require_role_management_authority(
                org_id,
                actor_user_id,
                target_role=str(member.role),
            )

        AuditLogService(self.db).record(
            actor_user_id=actor_user_id,
            action="member_removed",
            target_type="membership",
            target_id=member.id,
            organization_id=org_id,
            metadata_json={"user_id": str(user_id), "role": str(member.role)},
        )
        await self.db.delete(member)
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()
        return True

    async def update_role(
        self,
        org_id: UUID,
        user_id: UUID,
        new_role: str,
        *,
        actor_user_id: UUID | None = None,
        commit: bool = True,
    ) -> OrganizationMember | None:
        if actor_user_id is not None:
            await self._require_role_management_authority(
                org_id,
                actor_user_id,
                target_role=new_role,
            )

        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return None

        if member.role == "owner" and new_role != "owner":
            raise ValueError("Cannot change owner role")

        if actor_user_id is not None and str(member.role) == "admin":
            await self._require_role_management_authority(
                org_id,
                actor_user_id,
                target_role="admin",
            )

        previous_role = str(member.role)
        member.role = MemberRole(new_role)
        AuditLogService(self.db).record(
            actor_user_id=actor_user_id,
            action="member_role_updated",
            target_type="membership",
            target_id=member.id,
            organization_id=org_id,
            metadata_json={
                "user_id": str(user_id),
                "previous_role": previous_role,
                "new_role": str(new_role),
            },
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(member)
        else:
            await self.db.flush()
        return member

    async def get_member(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
            )
        )
        return result.scalar_one_or_none()

    async def list_members(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[OrganizationMember], int]:
        count_result = await self.db.execute(
            select(func.count(OrganizationMember.id))
            .where(OrganizationMember.organization_id == str(org_id))
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(OrganizationMember.organization_id == str(org_id))
            .order_by(OrganizationMember.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        members = list(result.scalars().all())

        return members, total

    async def create_invitation(
        self,
        org_id: UUID,
        inviter_user_id: UUID,
        data: MemberInvite,
        *,
        commit: bool = True,
    ) -> tuple[OrganizationInvitation, str]:
        await self._require_role_management_authority(
            org_id,
            inviter_user_id,
            target_role=data.role,
        )
        normalized_email = data.email.strip().lower()
        existing_member = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == str(org_id),
                func.lower(User.email) == normalized_email,
            )
        )
        if existing_member.scalar_one_or_none() is not None:
            raise ValueError("User is already a member of this organization")

        raw_token = secrets.token_urlsafe(32)
        invitation = OrganizationInvitation(
            organization_id=str(org_id),
            email=normalized_email,
            role=data.role,
            token_hash=_hash_invitation_token(raw_token),
            status="pending",
            invited_by_user_id=str(inviter_user_id),
            expires_at=datetime.now(UTC) + timedelta(days=INVITATION_TTL_DAYS),
        )
        self.db.add(invitation)
        await self.db.flush()
        AuditLogService(self.db).record(
            actor_user_id=inviter_user_id,
            action="invitation_created",
            target_type="invitation",
            target_id=invitation.id,
            organization_id=org_id,
            metadata_json={"email": normalized_email, "role": data.role},
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(invitation)
        return invitation, raw_token

    async def accept_invitation(
        self,
        org_id: UUID,
        invitation_id: UUID | str,
        accepting_user_id: UUID,
        token: str,
        *,
        commit: bool = True,
    ) -> OrganizationMember:
        user_result = await self.db.execute(
            select(User).where(
                User.id == str(accepting_user_id),
                User.is_active.is_(True),
            )
        )
        user = user_result.scalar_one_or_none()
        if user is None or not user.email:
            raise MembershipAuthorizationError("Authenticated user must have a verified active email")

        inv_result = await self.db.execute(
            select(OrganizationInvitation).where(
                OrganizationInvitation.id == str(invitation_id),
                OrganizationInvitation.organization_id == str(org_id),
            )
        )
        invitation = inv_result.scalar_one_or_none()
        if invitation is None:
            raise ValueError("Invitation not found")
        if invitation.status != "pending":
            raise ValueError("Invitation is no longer pending")

        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            invitation.status = "expired"
            await self.db.flush()
            raise ValueError("Invitation has expired")

        expected_hash = _hash_invitation_token(token)
        if not hmac.compare_digest(invitation.token_hash, expected_hash):
            raise MembershipAuthorizationError("Invalid invitation token")

        if user.email.strip().lower() != invitation.email.strip().lower():
            raise MembershipAuthorizationError(
                "Authenticated user email does not match invitation email"
            )

        existing = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(accepting_user_id),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("User is already a member")

        invitation.status = "accepted"
        invitation.accepted_by_user_id = str(accepting_user_id)
        invitation.accepted_at = datetime.now(UTC)

        member = OrganizationMember(
            organization_id=str(org_id),
            user_id=str(accepting_user_id),
            role=invitation.role,
        )
        self.db.add(member)
        await self.db.flush()
        AuditLogService(self.db).record(
            actor_user_id=accepting_user_id,
            action="invitation_accepted",
            target_type="membership",
            target_id=member.id,
            organization_id=org_id,
            metadata_json={
                "invitation_id": str(invitation.id),
                "email": invitation.email,
                "role": str(invitation.role),
            },
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(member)
        return member

    async def transfer_ownership(
        self,
        org_id: UUID,
        current_owner_user_id: UUID,
        new_owner_user_id: UUID,
        *,
        commit: bool = True,
    ) -> OrganizationMember:
        actor = await self._get_active_actor_member(org_id, current_owner_user_id)
        if actor is None or actor.role != "owner":
            raise MembershipAuthorizationError("Only the current owner can transfer organization ownership")

        if str(current_owner_user_id) == str(new_owner_user_id):
            raise ValueError("New owner must be a different member")

        target = await self._get_active_actor_member(org_id, new_owner_user_id)
        if target is None:
            raise ValueError("Ownership transfer target user must be an existing member")

        actor.role = MemberRole.ADMIN
        await self.db.flush()
        target.role = MemberRole.OWNER
        await self.db.flush()

        AuditLogService(self.db).record(
            actor_user_id=current_owner_user_id,
            action="ownership_transferred",
            target_type="organization",
            target_id=org_id,
            organization_id=org_id,
            metadata_json={
                "previous_owner_user_id": str(current_owner_user_id),
                "new_owner_user_id": str(new_owner_user_id),
            },
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(target)
        return target

    async def invite_by_email(
        self,
        org_id: UUID,
        inviter_user_id: UUID,
        data: MemberInvite,
    ) -> OrganizationMember | None:
        await self._require_role_management_authority(
            org_id,
            inviter_user_id,
            target_role=data.role,
        )
        result = await self.db.execute(
            select(User).where(
                func.lower(User.email) == data.email.strip().lower(),
                User.is_active.is_(True),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        return await self.add_member(org_id, UUID(str(user.id)), data.role, actor_user_id=inviter_user_id)

