import json
import logging
from collections.abc import Callable
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.db.models import AuditLog
from app.db.session import AsyncSessionLocal
from app.middleware.redis_rate_limit import get_client_ip
from app.services.audit_logs import AuditLogService
from app.services.organizations import OrganizationService

AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
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
_audit_request_var: ContextVar[Request | None] = ContextVar("audit_request", default=None)


@event.listens_for(Session, "before_flush")
def _track_transactional_audit(session, _flush_context, _instances):
    request = _audit_request_var.get()
    if request is not None and any(isinstance(row, AuditLog) for row in session.new):
        session.info["audit_request"] = request


@event.listens_for(Session, "after_commit")
def _mark_committed_audit(session):
    if not session.in_nested_transaction():
        request = session.info.pop("audit_request", None)
        if request is not None:
            request.state.audit_recorded_in_tx = True


@event.listens_for(Session, "after_rollback")
def _discard_rolled_back_audit(session):
    session.info.pop("audit_request", None)


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

        token = _audit_request_var.set(request)
        try:
            response = await call_next(request)
        finally:
            _audit_request_var.reset(token)
        if response.status_code < 400 and getattr(request.state, "audit_recorded_in_tx", False):
            return response

        actor_user_id = getattr(request.state, "audit_user_id", None)
        actor_org_id = getattr(request.state, "audit_org_id", None)
        try:
            action = self._extract_action(request.method, path)
            target = self._extract_target(path)
            safe_path = getattr(request.scope.get("route"), "path", None) or self._redact_path(path)
            async with AsyncSessionLocal() as db:
                path_org_id = request.path_params.get("org_id")
                if path_org_id is not None:
                    # A URL is not tenant authority, even for an authenticated caller.
                    actor_org_id = None
                    try:
                        org_id = UUID(str(path_org_id))
                    except ValueError:
                        pass
                    else:
                        if actor_user_id and await OrganizationService(db).is_member(
                            org_id, UUID(actor_user_id)
                        ):
                            actor_org_id = str(org_id)
                await AuditLogService(db).create(
                    actor_user_id=UUID(actor_user_id) if actor_user_id else None,
                    action=action,
                    target_type=target.get("type", "unknown"),
                    target_id=target.get("id"),
                    organization_id=UUID(actor_org_id) if actor_org_id else None,
                    ip_address=get_client_ip(request, settings.trusted_proxy_ips_set),
                    user_agent=request.headers.get("user-agent"),
                    metadata_json={"method": request.method, "path": safe_path,
                                   "status_code": response.status_code},
                )
        except Exception:
            fields = {"event": "audit_write_failed", "method": request.method,
                      "status_code": response.status_code}
            logging.getLogger(__name__).warning(json.dumps(fields), extra=fields)

        return response

    def _redact_path(self, path: str) -> str:
        parts = [p for p in path.split("/") if p]
        redacted = []
        for part in parts:
            try:
                UUID(part)
            except ValueError:
                redacted.append(part if part in AUDITED_PATHS or part in {"api", "v1"} else "{value}")
            else:
                redacted.append("{id}")
        return "/" + "/".join(redacted)

    def _extract_action(self, method: str, _path: str) -> str:
        action_map = {
            "POST": "create",
            "PATCH": "update",
            "PUT": "update",
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
            "suppression-rules": "suppression_rule",
            "schedules": "schedule",
        }
        target_type = "unknown"
        target_id = None

        for i in range(len(parts) - 1, -1, -1):
            part = parts[i]
            if part in target_types:
                target_type = target_types[part]
                if i + 1 == len(parts):
                    break
                potential_id = parts[i + 1]
                try:
                    UUID(potential_id)
                    target_id = potential_id
                except ValueError:
                    pass
                break

        return {"type": target_type, "id": target_id}
