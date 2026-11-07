"""The API's capability map must agree with the worker's registry (review S3).

The apps never import each other, so the worker map is read from its source file as a literal.
The only permitted difference is the API's "osv-scanner" alias for the worker's "osv" adapter.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.evidence_contract import CAPABILITY_SCANNERS

REGISTRY = Path(__file__).resolve().parents[2] / "worker" / "app" / "scanners" / "registry.py"
API_ONLY_ALIASES = {"osv-scanner"}


def _worker_capability_registry() -> dict[str, list[str]]:
    tree = ast.parse(REGISTRY.read_text())
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "CAPABILITY_REGISTRY":
            return ast.literal_eval(node.value)
    raise AssertionError("CAPABILITY_REGISTRY not found in the worker registry")


@pytest.mark.skipif(not REGISTRY.exists(), reason="worker app not present in this checkout")
def test_api_and_worker_capability_maps_agree_apart_from_the_osv_alias():
    api = {capability: set(scanners) - API_ONLY_ALIASES for capability, scanners in CAPABILITY_SCANNERS.items()}
    worker = {capability: set(scanners) for capability, scanners in _worker_capability_registry().items()}

    assert api == worker
    assert {a for scanners in CAPABILITY_SCANNERS.values() for a in scanners} >= API_ONLY_ALIASES
