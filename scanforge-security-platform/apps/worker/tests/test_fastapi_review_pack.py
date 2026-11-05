"""P2.4 (#52): FastAPI framework review pack.

The pack is a tested context strategy, not a claim of comprehensive detection:
detection gates activation, a retrieval recipe finds the dependencies that
establish identity and organization scope, curated Semgrep rules raise
authorization and tenant-scope questions, and legitimate patterns must not fire.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.review_packs import detect_review_packs
from app.review_packs.fastapi_pack import (
    PACK_ID,
    PACK_VERSION,
    RULES_PATH,
    UNSUPPORTED_CASES,
    retrieve_context,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "review_packs"
FASTAPI_FIXTURES = FIXTURES / "fastapi"
SEMGREP = shutil.which("semgrep")


def _copy(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst)
    return dst


def _run_pack_rules(target: Path) -> list[dict]:
    completed = subprocess.run(  # noqa: S603
        [
            SEMGREP,
            "scan",
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "--config",
            str(RULES_PATH),
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode in (0, 1), completed.stderr
    return json.loads(completed.stdout)["results"]


def _rule_ids_by_file(results: list[dict]) -> dict[str, set[str]]:
    by_file: dict[str, set[str]] = {}
    for item in results:
        by_file.setdefault(Path(item["path"]).name, set()).add(item["check_id"].rsplit(".", 1)[-1])
    return by_file


# --- Detection --------------------------------------------------------------


def test_detection_activates_for_a_fastapi_repository(tmp_path):
    repo = _copy(FASTAPI_FIXTURES / "vulnerable", tmp_path / "repo")

    packs = detect_review_packs(repo)

    assert [pack.pack_id for pack in packs] == [PACK_ID]
    assert packs[0].version == PACK_VERSION
    assert "no_auth_routes.py" in " ".join(packs[0].evidence)


@pytest.mark.parametrize("fixture", ["flask_app", "mentions_only"])
def test_detection_ignores_non_fastapi_repositories(tmp_path, fixture):
    repo = _copy(FIXTURES / "not_fastapi" / fixture, tmp_path / "repo")

    assert detect_review_packs(repo) == []


def test_detection_ignores_vendored_and_hidden_directories(tmp_path):
    repo = tmp_path / "repo"
    (repo / "node_modules" / "x").mkdir(parents=True)
    (repo / ".venv" / "lib").mkdir(parents=True)
    source = "from fastapi import FastAPI\napp = FastAPI()\n"
    (repo / "node_modules" / "x" / "app.py").write_text(source)
    (repo / ".venv" / "lib" / "app.py").write_text(source)

    assert detect_review_packs(repo) == []


def test_detection_survives_unparseable_python(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "broken.py").write_text("def (:\n")
    (repo / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

    assert [pack.pack_id for pack in detect_review_packs(repo)] == [PACK_ID]


# --- Rules ------------------------------------------------------------------


@pytest.fixture(scope="module")
def rule_results(tmp_path_factory) -> dict[str, list[dict]]:
    """One Semgrep run over both fixture sets (a run costs ~25 s of startup)."""
    root = tmp_path_factory.mktemp("pack_rules")
    _copy(FASTAPI_FIXTURES / "vulnerable", root / "vulnerable")
    _copy(FASTAPI_FIXTURES / "legitimate", root / "legitimate")
    results = _run_pack_rules(root)
    return {
        "vulnerable": [r for r in results if "/vulnerable/" in r["path"]],
        "legitimate": [r for r in results if "/legitimate/" in r["path"]],
    }


@pytest.mark.skipif(SEMGREP is None, reason="semgrep binary not installed")
def test_rules_fire_on_each_vulnerable_fixture(rule_results):
    assert _rule_ids_by_file(rule_results["vulnerable"]) == {
        "no_auth_routes.py": {"fastapi-route-without-auth-dependency"},
        "unscoped_lookup.py": {"fastapi-unscoped-primary-key-lookup"},
        "client_supplied_org.py": {"fastapi-client-supplied-organization-id"},
    }


@pytest.mark.skipif(SEMGREP is None, reason="semgrep binary not installed")
def test_unauthenticated_route_rule_flags_both_handlers(rule_results):
    lines = [r for r in rule_results["vulnerable"] if r["path"].endswith("no_auth_routes.py")]

    assert len(lines) == 2


@pytest.mark.skipif(SEMGREP is None, reason="semgrep binary not installed")
def test_rules_never_fire_on_legitimate_patterns(rule_results):
    assert rule_results["legitimate"] == []


@pytest.mark.skipif(SEMGREP is None, reason="semgrep binary not installed")
def test_rule_findings_are_questions_not_verdicts(rule_results):
    assert rule_results["vulnerable"]
    for item in rule_results["vulnerable"]:
        extra = item["extra"]
        assert extra["metadata"]["review_pack"] == PACK_ID
        assert extra["metadata"]["pack_version"] == PACK_VERSION
        assert extra["severity"] == "INFO"
        assert extra["metadata"]["confidence"] == "LOW"
        assert "?" in extra["message"]


# --- Context retrieval ------------------------------------------------------


def test_context_recipe_finds_identity_and_organization_scope_dependencies(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "deps.py").write_text(
        "from fastapi import Depends\n"
        "from fastapi.security import OAuth2PasswordBearer\n"
        "oauth2 = OAuth2PasswordBearer(tokenUrl='token')\n"
        "\n"
        "async def get_current_user(token=Depends(oauth2)):\n"
        "    return token\n"
        "\n"
        "async def require_org_member(organization_id: str, user=Depends(get_current_user)):\n"
        "    return user\n"
        "\n"
        "async def get_db():\n"
        "    yield None\n"
    )
    (repo / "routes.py").write_text(
        "from fastapi import APIRouter, Depends, FastAPI\n"
        "from deps import get_current_user, require_org_member, get_db\n"
        "app = FastAPI()\n"
        "router = APIRouter()\n"
        "@router.get('/a')\n"
        "async def a(user=Depends(get_current_user), m=Depends(require_org_member), db=Depends(get_db)):\n"
        "    return 1\n"
        "app.include_router(router, dependencies=[Depends(get_current_user)])\n"
    )

    context = retrieve_context(repo)
    by_name = {(item["name"], item["role"]) for item in context}

    assert ("get_current_user", "identity") in by_name
    assert ("require_org_member", "organization_scope") in by_name
    assert ("get_current_user", "router_level_dependency") in by_name
    assert not any(item["name"] == "get_db" for item in context)
    definition = next(
        item for item in context if item["name"] == "get_current_user" and item["role"] == "identity"
    )
    assert definition["path"] == "deps.py"
    assert definition["line"] == 5


def test_context_recipe_is_bounded_and_deterministic(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    body = "from fastapi import Depends\n" + "".join(
        f"def get_current_user_{i}():\n    return {i}\n\n"
        f"def use_{i}(u=Depends(get_current_user_{i})):\n    return u\n\n"
        for i in range(200)
    )
    (repo / "deps.py").write_text(body)

    first = retrieve_context(repo)
    second = retrieve_context(repo)

    assert first == second
    assert 0 < len(first) <= 50


# --- Versioning and documented limits ---------------------------------------


def test_pack_record_carries_version_and_rules_digest(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "from fastapi import Depends, FastAPI\n"
        "app = FastAPI()\n"
        "def get_current_user():\n    return 1\n"
        "@app.get('/x')\n"
        "def x(u=Depends(get_current_user)):\n    return u\n"
    )

    record = detect_review_packs(repo)[0].to_record()

    assert record["id"] == "fastapi"
    assert record["version"] == PACK_VERSION
    assert record["rules_digest"].startswith("sha256:")
    assert record["context"]


def test_unsupported_cases_are_documented():
    assert len(UNSUPPORTED_CASES) >= 4
    assert all(isinstance(case, str) and case for case in UNSUPPORTED_CASES)
    joined = " ".join(UNSUPPORTED_CASES).lower()
    assert "include_router" in joined
    assert "comprehensive" in joined
