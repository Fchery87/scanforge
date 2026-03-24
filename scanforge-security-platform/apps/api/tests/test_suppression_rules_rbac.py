from app.api.v1.routes.suppression_rules import router


def test_create_suppression_has_auth_dependency():
    """Verify create endpoint requires authentication."""
    create_route = next(
        r for r in router.routes if r.path == "/organizations/{org_id}/suppression-rules" and "POST" in r.methods
    )
    # The route should have auth via Depends(get_current_user) in the function signature
    assert any("get_current_user" in str(d) or "Depends" in str(d) for d in create_route.dependant.dependencies), (
        "Create suppression rule must require authentication"
    )


def test_list_suppressions_has_auth_dependency():
    """Verify list endpoint requires authentication."""
    list_route = next(
        r for r in router.routes if r.path == "/organizations/{org_id}/suppression-rules" and "GET" in r.methods
    )
    assert any("get_current_user" in str(d) or "Depends" in str(d) for d in list_route.dependant.dependencies), (
        "List suppression rules must require authentication"
    )


def test_update_suppression_has_auth_dependency():
    """Verify update endpoint requires authentication."""
    update_route = next(
        r
        for r in router.routes
        if r.path == "/organizations/{org_id}/suppression-rules/{rule_id}" and "PATCH" in r.methods
    )
    assert any("get_current_user" in str(d) or "Depends" in str(d) for d in update_route.dependant.dependencies), (
        "Update suppression rule must require authentication"
    )


def test_delete_suppression_has_auth_dependency():
    """Verify delete endpoint requires authentication."""
    delete_route = next(
        r
        for r in router.routes
        if r.path == "/organizations/{org_id}/suppression-rules/{rule_id}" and "DELETE" in r.methods
    )
    assert any("get_current_user" in str(d) or "Depends" in str(d) for d in delete_route.dependant.dependencies), (
        "Delete suppression rule must require authentication"
    )
