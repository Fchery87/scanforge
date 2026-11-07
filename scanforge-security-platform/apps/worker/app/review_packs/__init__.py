"""Framework review packs: detection-gated context strategies for shadow PR review."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.review_packs import fastapi_pack

if TYPE_CHECKING:
    from pathlib import Path

    from app.review_packs.fastapi_pack import ActiveReviewPack


def detect_review_packs(repo_path: Path) -> list[ActiveReviewPack]:
    """Return the packs whose detection matches ``repo_path``, in registry order."""
    packs: list[ActiveReviewPack] = []
    evidence = fastapi_pack.detect(repo_path)
    if evidence:
        packs.append(
            fastapi_pack.ActiveReviewPack(
                pack_id=fastapi_pack.PACK_ID,
                version=fastapi_pack.PACK_VERSION,
                rules_path=fastapi_pack.RULES_PATH,
                rules_relative_path=fastapi_pack.RULES_RELATIVE_PATH,
                rules_digest=fastapi_pack.rules_digest(),
                evidence=tuple(evidence),
                context=tuple(fastapi_pack.retrieve_context(repo_path)),
            )
        )
    return packs
