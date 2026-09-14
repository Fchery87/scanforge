"""Allowlisted environments for subprocesses the worker spawns.

Scanners and git subprocesses must never inherit the worker process
environment: it carries API database URLs, worker credentials, webhook
secrets, and object-storage keys that have no business inside a scan.
"""
from __future__ import annotations

import os

ALLOWED_ENV_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
    }
)


def build_contained_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the only environment a scanner/clone subprocess may see."""
    env = {key: os.environ[key] for key in sorted(ALLOWED_ENV_KEYS) if key in os.environ}
    if extra:
        env.update(extra)
    return env
