from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import AuditLog, Organization, OrganizationMember, User
from app.schemas.memberships import MemberInvite
from app.services.memberships import MembershipAuthorizationError, MembershipService
from app.services.organizations import OrganizationService


from sqlalchemy.types import CHAR, TypeDecorator


@compiles(PGUUID, "sqlite")
def _pg_uuid_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(64)"


class _SQLiteUUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def bind_processor(self, dialect):
        if dialect.name == "postgresql":
            return None

        def process(value):
            if value is None:
                return None
            return str(value)

        return process


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


@pytest.fixture
async def db_session():
    _downcast_postgres_uuid_columns()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed_org_with_owner_and_admin(db_session):
    owner_id = uuid4()
    admin_id = uuid4()
    invitee_id = uuid4()
    org_id = uuid4()
    db_session.add_all(
        [
            User(
                id=str(owner_id),
                auth_provider_user_id="sub-owner",
                email="owner@acme.example",
                name="Owner",
                is_active=True,
            ),
            User(
                id=str(admin_id),
                auth_provider_user_id="sub-admin",
                email="admin@acme.example",
                name="Admin",
                is_active=True,
            ),
            User(
                id=str(invitee_id),
                auth_provider_user_id="sub-invitee",
                email="invitee@acme.example",
                name="Invitee",
                is_active=True,
            ),
            Organization(
                id=str(org_id),
                name="Acme",
                slug="acme",
                created_by_user_id=str(owner_id),
            ),
            OrganizationMember(
                id=str(uuid4()),
                organization_id=str(org_id),
                user_id=str(owner_id),
                role="owner",
            ),
            OrganizationMember(
                id=str(uuid4()),
                organization_id=str(org_id),
                user_id=str(admin_id),
                role="admin",
            ),
        ]
    )
    await db_session.commit()
    return org_id, owner_id, admin_id, invitee_id


@pytest.mark.asyncio
async def test_no_admin_shortcut_for_owner_only_permission(db_session):
    org_id, owner_id, admin_id, _invitee_id = await _seed_org_with_owner_and_admin(db_session)
    org_service = OrganizationService(db_session)

    assert await org_service.user_has_permission(org_id, owner_id, ["owner"]) is True
    assert await org_service.user_has_permission(org_id, admin_id, ["owner"]) is False
    assert await org_service.user_has_permission(org_id, admin_id, ["owner", "admin"]) is True


@pytest.mark.asyncio
async def test_admin_cannot_appoint_or_remove_admin(db_session):
    org_id, owner_id, admin_id, invitee_id = await _seed_org_with_owner_and_admin(db_session)
    service = MembershipService(db_session)

    with pytest.raises(MembershipAuthorizationError, match="Only owners"):
        await service.create_invitation(
            org_id,
            inviter_user_id=admin_id,
            data=MemberInvite(email="invitee@acme.example", role="admin"),
        )

    other_admin_id = uuid4()
    db_session.add_all(
        [
            User(
                id=str(other_admin_id),
                auth_provider_user_id="sub-admin-2",
                email="admin2@acme.example",
                name="Admin 2",
                is_active=True,
            ),
            OrganizationMember(
                id=str(uuid4()),
                organization_id=str(org_id),
                user_id=str(other_admin_id),
                role="admin",
            ),
        ]
    )
    await db_session.commit()

    with pytest.raises(MembershipAuthorizationError, match="Only owners"):
        await service.remove_member(org_id, other_admin_id, actor_user_id=admin_id)

    with pytest.raises(MembershipAuthorizationError, match="Only owners"):
        await service.update_role(org_id, invitee_id, "admin", actor_user_id=admin_id)

    assert owner_id != admin_id


@pytest.mark.asyncio
async def test_pending_invitation_requires_verified_matching_email_acceptance(db_session):
    org_id, _owner_id, admin_id, invitee_id = await _seed_org_with_owner_and_admin(db_session)
    wrong_user_id = uuid4()
    db_session.add(
        User(
            id=str(wrong_user_id),
            auth_provider_user_id="sub-wrong",
            email="other@acme.example",
            name="Other",
            is_active=True,
        )
    )
    await db_session.commit()

    service = MembershipService(db_session)
    invitation, raw_token = await service.create_invitation(
        org_id,
        inviter_user_id=admin_id,
        data=MemberInvite(email="invitee@acme.example", role="developer"),
    )

    # Before acceptance, invitee is NOT yet a member.
    assert await service.get_member(org_id, invitee_id) is None

    # Wrong user with different email cannot accept the invitation.
    with pytest.raises(MembershipAuthorizationError, match="email"):
        await service.accept_invitation(
            org_id,
            invitation.id,
            accepting_user_id=wrong_user_id,
            token=raw_token,
        )
    assert await service.get_member(org_id, wrong_user_id) is None

    # Correct user accepts the pending invitation and becomes an active member.
    member = await service.accept_invitation(
        org_id,
        invitation.id,
        accepting_user_id=invitee_id,
        token=raw_token,
    )
    assert member.user_id == str(invitee_id)
    assert member.role == "developer"


@pytest.mark.asyncio
async def test_atomic_ownership_transfer_preserves_single_owner(db_session):
    org_id, owner_id, admin_id, invitee_id = await _seed_org_with_owner_and_admin(db_session)
    service = MembershipService(db_session)

    # Non-owner cannot transfer ownership.
    with pytest.raises(MembershipAuthorizationError, match="Only the current owner"):
        await service.transfer_ownership(
            org_id,
            current_owner_user_id=admin_id,
            new_owner_user_id=owner_id,
        )

    # Cannot transfer ownership to non-member.
    with pytest.raises(ValueError, match="target user must be an existing member"):
        await service.transfer_ownership(
            org_id,
            current_owner_user_id=owner_id,
            new_owner_user_id=invitee_id,
        )

    # Atomic transfer from owner_id -> admin_id.
    new_owner_member = await service.transfer_ownership(
        org_id,
        current_owner_user_id=owner_id,
        new_owner_user_id=admin_id,
    )
    assert new_owner_member.user_id == str(admin_id)
    assert new_owner_member.role == "owner"

    former_owner = await service.get_member(org_id, owner_id)
    assert former_owner is not None
    assert former_owner.role == "admin"

    owners = (
        await db_session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.role == "owner",
            )
        )
    ).scalars().all()
    assert len(owners) == 1
    assert owners[0].user_id == str(admin_id)

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.organization_id == str(org_id),
                AuditLog.action == "ownership_transferred",
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1
