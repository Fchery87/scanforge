"""FastAPI framework review pack (P2.4, #52).

A tested context strategy for shadow PR review, not a claim of comprehensive
detection. The pack contributes four things:

* detection: the pack activates only for repositories that construct a
  ``FastAPI`` app or ``APIRouter`` in Python source;
* a deterministic, bounded context-retrieval recipe that locates the
  dependencies establishing identity and organization scope;
* curated, versioned Semgrep rules (``rules/packs/fastapi-authorization.yml``)
  that raise authorization and tenant-scope *questions* (ADR-017: candidates,
  never decisions);
* documented unsupported cases (``UNSUPPORTED_CASES``).

Bump ``PACK_VERSION`` whenever detection, the recipe or the rules change; the
version is recorded on every run that uses the pack.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

PACK_ID = "fastapi"
PACK_VERSION = "fastapi.v1"
RULES_RELATIVE_PATH = Path("packs") / "fastapi-authorization.yml"
RULES_PATH = Path(__file__).resolve().parents[1] / "scanners" / "rules" / RULES_RELATIVE_PATH

MAX_PYTHON_FILES = 5000
MAX_FILE_BYTES = 512 * 1024
MAX_EVIDENCE_PATHS = 5
MAX_CONTEXT_ENTRIES = 50

_SKIPPED_DIRECTORIES = frozenset(
    {"node_modules", "venv", "env", "site-packages", "__pycache__", "build", "dist", "vendor"}
)
_APP_CONSTRUCTORS = frozenset({"FastAPI", "APIRouter"})
_DEPENDENCY_MARKERS = frozenset({"Depends", "Security"})
_IDENTITY_NAME = re.compile(
    r"current_user|get_user|authenticate|(^|_)auth(_|$)|verify_token|require_user|principal|get_current",
    re.IGNORECASE,
)
_IDENTITY_SYMBOLS = frozenset(
    {
        "OAuth2PasswordBearer",
        "OAuth2AuthorizationCodeBearer",
        "HTTPBearer",
        "HTTPBasic",
        "APIKeyHeader",
        "APIKeyCookie",
        "APIKeyQuery",
        "SecurityScopes",
    }
)
_ORG_SCOPE_NAME = re.compile(r"org|tenant|workspace|member|role|permission", re.IGNORECASE)
_ORG_PARAMETER = re.compile(r"^(organization|org|tenant|workspace)_id$")

UNSUPPORTED_CASES: tuple[str, ...] = (
    "Not a comprehensive detector: the rules ask authorization and tenant-scope questions for a reviewer; "
    "a clean result says nothing about the absence of authorization defects.",
    "Router-level dependencies attached in another file (app.include_router(..., dependencies=[...]) or an "
    "APIRouter constructed elsewhere) are invisible to the rules and can cause route-without-auth false "
    "positives; the context recipe reports include_router/APIRouter dependencies so a reviewer can check.",
    "Authorization enforced by middleware, ASGI wrappers, API gateways or a reverse proxy is not modelled.",
    "Dependencies reached through non-literal indirection (dependency factories returning closures, "
    "dynamically built dependency lists, dependency_overrides) are not resolved.",
    "Tenant scoping delegated to service or repository helpers (for example service.get(org_id, item_id)) "
    "is not inspected; only direct session.get(Model, <handler parameter>) lookups are questioned.",
    "Row-level security, database policies and ORM-level default filters are not modelled.",
    "Only Python source is analysed: non-Python services and generated clients are out of scope, as are "
    "WebSocket routes and Starlette-only routing.",
    "Detection is limited to the first MAX_PYTHON_FILES Python files under the repository, excluding "
    "hidden, vendored and virtual-environment directories.",
)


@dataclass(frozen=True)
class ActiveReviewPack:
    pack_id: str
    version: str
    rules_path: Path
    rules_relative_path: Path
    rules_digest: str
    evidence: tuple[str, ...]
    context: tuple[dict, ...]

    def to_record(self) -> dict:
        """Run-level record: which pack, which version, which rules, and why it activated."""
        return {
            "id": self.pack_id,
            "version": self.version,
            "rules_digest": self.rules_digest,
            "evidence": list(self.evidence),
            "context": [dict(item) for item in self.context],
        }


def rules_digest() -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(RULES_PATH.read_bytes()).hexdigest()


def _python_files(repo_path: Path) -> list[Path]:
    root = Path(repo_path)
    found: list[Path] = []
    stack = [root]
    while stack and len(found) < MAX_PYTHON_FILES:
        directory = stack.pop()
        try:
            entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            name = entry.name
            if entry.is_dir():
                if name.startswith(".") or name in _SKIPPED_DIRECTORIES:
                    continue
                stack.append(entry)
            elif name.endswith(".py"):
                found.append(entry)
    return sorted(found)


def _parse(path: Path) -> ast.Module | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return ast.parse(path.read_bytes())
    except (OSError, SyntaxError, ValueError, RecursionError):
        return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _constructs_app(tree: ast.Module) -> bool:
    imports_fastapi = any(
        (isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "fastapi")
        or (isinstance(node, ast.Import) and any(alias.name.split(".")[0] == "fastapi" for alias in node.names))
        for node in ast.walk(tree)
    )
    if not imports_fastapi:
        return False
    return any(
        isinstance(node, ast.Call) and _call_name(node.func) in _APP_CONSTRUCTORS for node in ast.walk(tree)
    )


def _relative(repo_path: Path, path: Path) -> str:
    return path.relative_to(repo_path).as_posix()


def detect(repo_path: Path) -> list[str]:
    """Return repository-relative evidence paths; empty means the repository is not FastAPI."""
    repo = Path(repo_path)
    evidence: list[str] = []
    for path in _python_files(repo):
        tree = _parse(path)
        if tree is not None and _constructs_app(tree):
            evidence.append(_relative(repo, path))
            if len(evidence) >= MAX_EVIDENCE_PATHS:
                break
    return evidence


def _dependency_targets(call: ast.Call) -> list[str]:
    """Names passed to Depends(...)/Security(...) anywhere inside a call's arguments."""
    names: list[str] = []
    for node in ast.walk(call):
        if isinstance(node, ast.Call) and _call_name(node.func) in _DEPENDENCY_MARKERS and node.args:
            target = _call_name(node.args[0])
            if target:
                names.append(target)
    return names


def _classify(definition: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    parameters = [arg.arg for arg in definition.args.args + definition.args.kwonlyargs]
    if _ORG_SCOPE_NAME.search(definition.name) or any(_ORG_PARAMETER.match(p) for p in parameters):
        return "organization_scope"
    symbols = {
        _call_name(node)
        for node in ast.walk(definition)
        if isinstance(node, (ast.Name, ast.Attribute))
    }
    if _IDENTITY_NAME.search(definition.name) or symbols & _IDENTITY_SYMBOLS:
        return "identity"
    return None


def retrieve_context(repo_path: Path) -> list[dict]:
    """Locate the dependencies that establish identity and organization scope.

    Deterministic and bounded: results are sorted by (path, line, role, name) and
    capped at ``MAX_CONTEXT_ENTRIES``. Each entry is ``{name, role, path, line}``
    with role ``identity``, ``organization_scope`` or ``router_level_dependency``.
    """
    repo = Path(repo_path)
    definitions: list[tuple[str, str, int, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    used: set[str] = set()
    router_level: list[dict] = []
    for path in _python_files(repo):
        tree = _parse(path)
        if tree is None:
            continue
        relative = _relative(repo, path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions.append((node.name, relative, node.lineno, node))
            elif isinstance(node, ast.Call):
                used.update(_dependency_targets(node))
                keyword_dependencies = [kw for kw in node.keywords if kw.arg == "dependencies"]
                if _call_name(node.func) in {"include_router", "add_api_route", *_APP_CONSTRUCTORS}:
                    for keyword in keyword_dependencies:
                        holder = ast.Call(func=node.func, args=[keyword.value], keywords=[])
                        for target in _dependency_targets(holder):
                            router_level.append(
                                {
                                    "name": target,
                                    "role": "router_level_dependency",
                                    "path": relative,
                                    "line": node.lineno,
                                }
                            )
    entries = list(router_level)
    for name, relative, line, node in definitions:
        if name not in used:
            continue
        role = _classify(node)
        if role is not None:
            entries.append({"name": name, "role": role, "path": relative, "line": line})
    entries.sort(key=lambda item: (item["path"], item["line"], item["role"], item["name"]))
    return entries[:MAX_CONTEXT_ENTRIES]
