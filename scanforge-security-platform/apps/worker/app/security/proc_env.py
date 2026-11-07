"""Allowlisted environments for subprocesses the worker spawns.

Scanners and git subprocesses must never inherit the worker process
environment: it carries API database URLs, worker credentials, webhook
secrets, and object-storage keys that have no business inside a scan.
"""
from __future__ import annotations

import os
from pathlib import Path

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


def build_git_env(*, auth_header: str, home_dir: Path, allow_file_protocol: bool = False) -> dict[str, str]:
    """Environment for git subprocesses that operate on untrusted repositories.

    Host system/global configuration (filter drivers, URL rewrites, fsmonitor,
    credential helpers) must not apply, and only HTTPS transport is allowed.
    The auth header, when present, is always config index 0 so callers can
    scrub GIT_CONFIG_VALUE_0 after use.
    """
    config: list[tuple[str, str]] = []
    if auth_header:
        config.append(("http.extraHeader", auth_header))
    config += [
        ("core.hooksPath", "/dev/null"),
        ("core.fsmonitor", "false"),
        ("protocol.allow", "never"),
        ("protocol.https.allow", "always"),
    ]
    if allow_file_protocol:
        config.append(("protocol.file.allow", "always"))

    env = build_contained_env(
        {
            "HOME": str(home_dir),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_CONFIG_COUNT": str(len(config)),
        }
    )
    for index, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    return env
