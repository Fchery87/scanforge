"""Location-stable finding identity (fp.v3) shared by source and secret normalizers.

Identity is repository + rule + normalized path + normalized-snippet digest +
occurrence index. Line numbers never enter the hash; they live on the
occurrence record only. Secret findings omit the snippet component entirely, so
no fingerprint can carry material derived from a secret value.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Hashable, Sequence
from pathlib import Path

from app.security.secret_evidence import redact_secret_patterns

SOURCE_FINGERPRINT_VERSION = "fp.v3"
_MAX_SNIPPET_BYTES = 64 * 1024
_WHITESPACE = re.compile(r"\s+")


def normalize_snippet(text: str) -> str:
    """Collapse whitespace after redacting recognizable secret material."""
    return _WHITESPACE.sub(" ", redact_secret_patterns(text)).strip()


def snippet_digest(text: str) -> str:
    return hashlib.sha256(normalize_snippet(text).encode()).hexdigest()


def read_snippet_digest(repo_root: Path, rel_path: str, line_start: int | None, line_end: int | None) -> str | None:
    """Digest the reported source lines, or None when they cannot be read safely.

    The path comes from scanner output, so it must resolve to a regular file
    inside the checkout (no traversal, no symlink escape).
    """
    if not rel_path or not isinstance(line_start, int) or line_start < 1:
        return None
    end = line_end if isinstance(line_end, int) and line_end >= line_start else line_start
    try:
        root = repo_root.resolve()
        target = (root / rel_path.lstrip("/")).resolve()
        target.relative_to(root)
        if not target.is_file() or target.stat().st_size > _MAX_SNIPPET_BYTES * 64:
            return None
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return None
    span = lines[line_start - 1 : end]
    if not span:
        return None
    return snippet_digest("\n".join(span)[:_MAX_SNIPPET_BYTES])


def occurrence_indices(keys: Sequence[Hashable], positions: Sequence[tuple]) -> list[int]:
    """Index of each item among items sharing its key, in source order.

    Ties in position fall back to report order so the result is deterministic.
    """
    order = sorted(range(len(keys)), key=lambda i: (positions[i], i))
    seen: dict[Hashable, int] = {}
    indices = [0] * len(keys)
    for i in order:
        indices[i] = seen.get(keys[i], 0)
        seen[keys[i]] = indices[i] + 1
    return indices


def location_stable_fingerprint(
    *,
    scanner: str,
    repo_id: str,
    rule: str,
    path: str,
    occurrence_index: int,
    snippet_sha256: str | None = None,
) -> str:
    components = [SOURCE_FINGERPRINT_VERSION, scanner, repo_id, rule, path]
    if snippet_sha256 is not None:
        components.append(snippet_sha256)
    components.append(str(occurrence_index))
    return hashlib.sha256("|".join(components).encode()).hexdigest()
