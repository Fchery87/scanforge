from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import access_policies


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.asyncio
async def test_get_project_in_org_for_user_returns_project_from_policy_query():
    project = SimpleNamespace(id=uuid4())

    class Db:
        async def execute(self, query):
            return ScalarResult(project)

    result = await access_policies.get_project_in_org_for_user(
        Db(),
        project_id=uuid4(),
        org_id=uuid4(),
        user_id=uuid4(),
    )

    assert result is project


@pytest.mark.asyncio
async def test_get_repository_in_project_for_user_returns_repository_from_policy_query():
    repo = SimpleNamespace(id=uuid4())

    class Db:
        async def execute(self, query):
            return ScalarResult(repo)

    result = await access_policies.get_repository_in_project_for_user(
        Db(),
        repo_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
    )

    assert result is repo
