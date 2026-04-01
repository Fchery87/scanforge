from app.api.v1.routes.organizations import router
from app.middleware.auth import get_current_user
from app.schemas.organizations import OrganizationSlugPreview


def test_slug_preview_route_exists_and_requires_authentication():
    route = next(
        r for r in router.routes if r.path == "/slug-preview" and "GET" in r.methods
    )

    assert route.response_model == OrganizationSlugPreview
    assert any(
        getattr(dependency, "call", None) is get_current_user
        for dependency in route.dependant.dependencies
    ), "Slug preview route must require authenticated user context"
