from app.api.v1.routes.findings_trend import router as findings_trend_router
from app.api.v1.routes.org_stats import router as org_stats_router
from app.api.v1.routes.scorecard import router as scorecard_router
from app.middleware.auth import get_current_user


def _has_auth_dependency(route) -> bool:
    return any(
        getattr(dependency, "call", None) is get_current_user
        for dependency in route.dependant.dependencies
    )


def test_org_stats_requires_authentication():
    route = next(
        r
        for r in org_stats_router.routes
        if r.path == "/organizations/{org_id}/stats" and "GET" in r.methods
    )

    assert _has_auth_dependency(route), "Organization stats must require authentication"


def test_project_scorecard_requires_authentication():
    route = next(
        r
        for r in scorecard_router.routes
        if r.path == "/organizations/{org_id}/projects/{project_id}/scorecard"
        and "GET" in r.methods
    )

    assert _has_auth_dependency(route), "Project scorecard must require authentication"


def test_findings_trend_requires_authentication():
    route = next(
        r
        for r in findings_trend_router.routes
        if r.path == "/organizations/{org_id}/projects/{project_id}/findings/trend"
        and "GET" in r.methods
    )

    assert _has_auth_dependency(route), "Findings trend must require authentication"
