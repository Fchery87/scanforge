#!/usr/bin/env python3
"""Advisory check: flag except Exception/bare except blocks without error logging.

Exits 0 always (advisory only). Run as part of CI to surface gaps.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOTS = [Path("apps/api/app"), Path("apps/worker/app")]

LOG_ATTRS = {"error", "warning", "critical", "exception"}
# Names that indicate structured error handling (return failure result, print to stderr, etc.)
HANDLED_NAMES = {"ScannerResult", "print"}


def _has_log_call(body: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in LOG_ATTRS:
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in HANDLED_NAMES:
                return True
    return False


def _reraises_as_http_exception(body: list[ast.stmt]) -> bool:
    """Return True if the handler re-raises as HTTPException (acceptable route pattern)."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                if exc.func.id == "HTTPException":
                    return True
    return False


def _is_bare_except(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name) and handler.type.id == "Exception":
        return True
    return False


issues: list[str] = []
script_root = Path(__file__).resolve().parent.parent.parent.parent

for root in ROOTS:
    for path in (script_root / root).rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if (
                    _is_bare_except(handler)
                    and not _has_log_call(handler.body)
                    and not _reraises_as_http_exception(handler.body)
                ):
                    rel = path.relative_to(script_root)
                    issues.append(f"{rel}:{handler.lineno}")

if issues:
    print("Advisory: except-without-logging (promote to error after cleanup pass):", file=sys.stderr)
    for issue in issues:
        print(f"  {issue}", file=sys.stderr)

sys.exit(0)
