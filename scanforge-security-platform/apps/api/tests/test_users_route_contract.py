from app.api.v1.routes.users import router
from app.middleware.auth import get_current_user
from app.schemas.auth import UserResponse


def test_users_me_route_exists_and_uses_real_user_response():
    route = next(
        r for r in router.routes if r.path == "/me" and "GET" in r.methods
    )

    assert route.response_model == UserResponse
    assert any(
        getattr(dependency, "call", None) is get_current_user
        for dependency in route.dependant.dependencies
    ), "Current user route must require authenticated user context"
