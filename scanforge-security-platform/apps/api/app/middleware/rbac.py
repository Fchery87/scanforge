from collections.abc import Callable
from enum import StrEnum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.middleware.auth import UserContext, get_current_user

security = HTTPBearer(auto_error=False)


class Permission(StrEnum):
    ORG_MANAGE = "org:manage"
    ORG_MEMBER_INVITE = "org:member:invite"
    ORG_MEMBER_REMOVE = "org:member:remove"
    ORG_SETTINGS_VIEW = "org:settings:view"
    ORG_SETTINGS_EDIT = "org:settings:edit"

    PROJECT_MANAGE = "project:manage"
    PROJECT_VIEW = "project:view"

    REPO_CONNECT = "repo:connect"
    REPO_DISCONNECT = "repo:disconnect"
    REPO_VIEW = "repo:view"

    SCAN_TRIGGER = "scan:trigger"
    SCAN_VIEW = "scan:view"
    SCAN_CANCEL = "scan:cancel"

    FINDING_VIEW = "finding:view"
    FINDING_SUPPRESS = "finding:suppress"
    FINDING_RESOLVE = "finding:resolve"

    EXPORT_CREATE = "export:create"
    EXPORT_VIEW = "export:view"

    ADMIN = "admin"


ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    "owner": list(Permission),
    "admin": [
        Permission.ORG_MEMBER_INVITE,
        Permission.ORG_MEMBER_REMOVE,
        Permission.ORG_SETTINGS_EDIT,
        Permission.PROJECT_MANAGE,
        Permission.REPO_CONNECT,
        Permission.REPO_DISCONNECT,
        Permission.SCAN_TRIGGER,
        Permission.SCAN_VIEW,
        Permission.SCAN_CANCEL,
        Permission.FINDING_VIEW,
        Permission.FINDING_SUPPRESS,
        Permission.FINDING_RESOLVE,
        Permission.EXPORT_CREATE,
        Permission.EXPORT_VIEW,
    ],
    "security_reviewer": [
        Permission.PROJECT_VIEW,
        Permission.REPO_VIEW,
        Permission.SCAN_VIEW,
        Permission.FINDING_VIEW,
        Permission.FINDING_SUPPRESS,
        Permission.EXPORT_CREATE,
        Permission.EXPORT_VIEW,
    ],
    "developer": [
        Permission.PROJECT_VIEW,
        Permission.REPO_VIEW,
        Permission.SCAN_TRIGGER,
        Permission.SCAN_VIEW,
        Permission.FINDING_VIEW,
        Permission.EXPORT_VIEW,
    ],
    "viewer": [
        Permission.PROJECT_VIEW,
        Permission.REPO_VIEW,
        Permission.SCAN_VIEW,
        Permission.FINDING_VIEW,
    ],
}


def has_permission(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, [])


def require_permission(permission: Permission) -> Callable:
    async def dependency(
        current_user: UserContext = Depends(get_current_user),
    ) -> UserContext:
        if not has_permission(current_user.role, permission):
            if current_user.role in {"owner", "admin"}:
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {permission}",
            )
        return current_user
    return dependency


def require_role(*roles: str) -> Callable:
    async def dependency(
        current_user: UserContext = Depends(get_current_user),
    ) -> UserContext:
        if current_user.role not in roles:
            if current_user.role in ("owner", "admin"):
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role not authorized. Required: {roles}",
            )
        return current_user
    return dependency
