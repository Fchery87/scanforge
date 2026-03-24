from fastapi import APIRouter

from app.api.v1.routes import (
    audit_logs,
    exports,
    findings,
    findings_trend,
    github,
    health,
    internal,
    memberships,
    notifications,
    org_stats,
    organizations,
    projects,
    repositories,
    scan_schedules,
    scans,
    scorecard,
    suppression_rules,
    webhooks,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(internal.router, tags=["internal"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(github.router, tags=["github"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(memberships.router, prefix="/organizations", tags=["memberships"])
api_router.include_router(org_stats.router, tags=["organizations"])
api_router.include_router(audit_logs.router, tags=["audit"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(projects.router, prefix="/organizations/{org_id}/projects", tags=["projects"])
api_router.include_router(
    repositories.router,
    prefix="/organizations/{org_id}/projects/{project_id}/repositories",
    tags=["repositories"],
)
api_router.include_router(
    scan_schedules.router,
    prefix="/organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/schedules",
    tags=["schedules"],
)
api_router.include_router(
    scans.router,
    prefix="/organizations/{org_id}/projects/{project_id}/scans",
    tags=["scans"],
)
api_router.include_router(
    findings.router,
    prefix="/organizations/{org_id}/projects/{project_id}/findings",
    tags=["findings"],
)
api_router.include_router(
    exports.router,
    prefix="/organizations/{org_id}/projects/{project_id}/exports",
    tags=["exports"],
)
api_router.include_router(scorecard.router, tags=["scorecard"])
api_router.include_router(suppression_rules.router, tags=["suppression-rules"])
api_router.include_router(findings_trend.router, tags=["findings"])
