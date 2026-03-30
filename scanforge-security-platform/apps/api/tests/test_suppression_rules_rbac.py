from app.api.v1.routes.suppression_rules import router
from app.middleware.auth import get_current_user


def _has_auth_dependency(route) -> bool:
    return any(getattr(dependency, "call", None) is get_current_user for dependency in route.dependant.dependencies)


def test_create_suppression_has_auth_dependency():
    """Verify create endpoint requires authentication."""
    create_route = next(
        r for r in router.routes if r.path == "/organizations/{org_id}/suppression-rules" and "POST" in r.methods
    )
    # The route should have auth via Depends(get_current_user) in the function signature
    assert _has_auth_dependency(create_route), (
        "Create suppression rule must require authentication"
    )


def test_list_suppressions_has_auth_dependency():
    """Verify list endpoint requires authentication."""
    list_route = next(
        r for r in router.routes if r.path == "/organizations/{org_id}/suppression-rules" and "GET" in r.methods
    )
    assert _has_auth_dependency(list_route), (
        "List suppression rules must require authentication"
    )


def test_update_suppression_has_auth_dependency():
    """Verify update endpoint requires authentication."""
    update_route = next(
        r
        for r in router.routes
        if r.path == "/organizations/{org_id}/suppression-rules/{rule_id}" and "PATCH" in r.methods
    )
    assert _has_auth_dependency(update_route), (
        "Update suppression rule must require authentication"
    )


def test_delete_suppression_has_auth_dependency():
    """Verify delete endpoint requires authentication."""
    delete_route = next(
        r
        for r in router.routes
        if r.path == "/organizations/{org_id}/suppression-rules/{rule_id}" and "DELETE" in r.methods
    )
    assert _has_auth_dependency(delete_route), (
        "Delete suppression rule must require authentication"
    )
