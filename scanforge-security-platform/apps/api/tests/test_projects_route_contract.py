from app.api.v1.routes.projects import router
from app.schemas.common import PaginatedResponse
from app.schemas.projects import ProjectWithStats


def test_list_projects_uses_stats_response_model():
    route = next(
        r for r in router.routes if r.path == "/" and "GET" in r.methods
    )

    assert route.response_model == PaginatedResponse[ProjectWithStats], (
        "Project list route must expose repo and finding stats to the dashboard"
    )
