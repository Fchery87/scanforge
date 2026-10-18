import logging
from collections.abc import Callable
from contextvars import ContextVar
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.db.session import AsyncSessionLocal
from app.services.audit_logs import AuditLogService

AUDITED_METHODS = {"POST", "PATCH", "DELETE"}
AUDITED_PATHS = [
    "/organizations",
    "/projects",
    "/repositories",
    "/scans",
    "/findings",
    "/exports",
    "/members",
    "/suppression-rules",
    "/schedules",
]

_audit_user_var: ContextVar[str | None] = ContextVar("audit_user_id", default=None)
_audit_org_var: ContextVar[str | None] = ContextVar("audit_org_id", default=None)


class AuditLogContext:
    @property
    def user_id(self) -> str | None:
        return _audit_user_var.get()

    @user_id.setter
    def user_id(self, value: str | None) -> None:
        _audit_user_var.set(value)

    @property
    def org_id(self) -> str | None:
        return _audit_org_var.get()

    @org_id.setter
    def org_id(self, value: str | None) -> None:
        _audit_org_var.set(value)

    def set(self, user_id: str | None = None, org_id: str | None = None):
        _audit_user_var.set(user_id)
        _audit_org_var.set(org_id)

    def clear(self):
        _audit_user_var.set(None)
        _audit_org_var.set(None)


audit_context = AuditLogContext()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in AUDITED_METHODS:
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(p) or f"/api/v1{p}" in path for p in AUDITED_PATHS):
            return await call_next(request)

        audit_context.clear()

        response = await call_next(request)
        if response.status_code >= 400 or getattr(request.state, "audit_recorded_in_tx", False):
            return response

        actor_user_id = getattr(request.state, "audit_user_id", None)
        actor_org_id = getattr(request.state, "audit_org_id", None)
        if actor_user_id:
            try:
                action = self._extract_action(request.method, path)
                target = self._extract_target(path)

                async with AsyncSessionLocal() as db:
                    service = AuditLogService(db)
                    await service.create(
                        actor_user_id=UUID(actor_user_id),
                        action=action,
                        target_type=target.get("type", "unknown"),
                        target_id=target.get("id"),
                        organization_id=UUID(actor_org_id) if actor_org_id else None,
                        ip_address=request.headers.get("x-forwarded-for", "").split(",")[0].strip() or None,
                        user_agent=request.headers.get("user-agent"),
                        metadata_json={
                            "method": request.method,
                            "path": path,
                            "status_code": response.status_code,
                        },
                    )
            except Exception:
                logger = logging.getLogger(__name__)
                logger.warning("audit write failed", exc_info=True)

        return response

    def _extract_action(self, method: str, _path: str) -> str:
        action_map = {
            "POST": "create",
            "PATCH": "update",
            "DELETE": "delete",
        }
        return action_map.get(method, method.lower())

    def _extract_target(self, path: str) -> dict:
        parts = [p for p in path.split("/") if p]
        target_types = {
            "organizations": "organization",
            "projects": "project",
            "repositories": "repository",
            "scans": "scan",
            "findings": "finding",
            "exports": "export",
            "members": "membership",
            "schedules": "schedule",
        }
        target_type = "unknown"
        target_id = None

        for i, part in enumerate(parts):
            if part in target_types and i + 1 < len(parts):
                target_type = target_types[part]
                potential_id = parts[i + 1]
                try:
                    UUID(potential_id)
                    target_id = potential_id
                except ValueError:
                    pass
                break

        return {"type": target_type, "id": target_id}
