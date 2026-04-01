from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.models.organization import Organization, OrganizationMember
from app.schemas.organizations import OrganizationCreate
from app.services.organizations import OrganizationService


@pytest.mark.asyncio
async def test_create_organization_auto_suffixes_taken_slug():
    user_id = uuid4()
    user = SimpleNamespace(id=user_id)
    captured = {}

    db = AsyncMock()
    db.add = Mock(side_effect=lambda model: captured.setdefault(type(model).__name__, []).append(model))
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: user),
        SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=uuid4())),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]

    service = OrganizationService(db)

    org, member = await service.create(
        OrganizationCreate(name="Studio Eighty7", slug="studio-eighty7"),
        user_id,
    )

    created_org = captured["Organization"][0]
    created_member = captured["OrganizationMember"][0]

    assert org is created_org
    assert member is created_member
    assert isinstance(created_org, Organization)
    assert created_org.slug == "studio-eighty7-2"
    assert isinstance(created_member, OrganizationMember)
    assert created_member.user_id == user_id


@pytest.mark.asyncio
async def test_get_available_slug_skips_to_next_open_suffix():
    db = AsyncMock()
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=uuid4())),
        SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=uuid4())),
        SimpleNamespace(scalar_one_or_none=lambda: None),
    ]

    service = OrganizationService(db)

    available_slug = await service.get_available_slug("studio-eighty7")

    assert available_slug == "studio-eighty7-3"
