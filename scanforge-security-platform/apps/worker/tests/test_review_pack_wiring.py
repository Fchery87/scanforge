"""#52: review packs run only in shadow PR analysis and are recorded on the run."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.review_packs.fastapi_pack import PACK_ID, PACK_VERSION, RULES_PATH
from app.scanners.base import ScannerResult
from app.scanners.semgrep import SemgrepAdapter
from app.services.scan_orchestrator import ScanContext, ScanOrchestrator
from app.services.scan_pipeline.execution import ScanExecutionStage
from app.services.scan_pipeline.persistence import PersistenceStage

FASTAPI_SOURCE = "from fastapi import FastAPI\napp = FastAPI()\n"
CONTAINER_PACK_RULES = "/opt/scanner-rules/packs/fastapi-authorization.yml"
PACK_RULES = (RULES_PATH, Path("packs/fastapi-authorization.yml"))


class RecordingSemgrep(SemgrepAdapter):
    instances: list = []

    def __init__(self) -> None:
        super().__init__()
        self.instances.append(self)

    def run(self, repo_path: Path) -> ScannerResult:
        return ScannerResult(scanner_name="semgrep", success=True, raw_output={"results": []})


def _context(repo: Path, *, pull_request_number: int | None) -> ScanContext:
    return ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch=None,
        commit_sha="a" * 40,
        job_id="job-1",
        repo_path=repo,
        pull_request_number=pull_request_number,
    )


async def _run(monkeypatch, context: ScanContext) -> None:
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    RecordingSemgrep.instances = []
    monkeypatch.setattr("app.services.scan_pipeline.execution.asyncio.to_thread", run_inline)
    monkeypatch.setattr("app.services.scan_pipeline.execution.scanners_for_scan_type", lambda _t: ["semgrep"])
    monkeypatch.setattr(
        "app.services.scan_pipeline.execution.SCANNER_REGISTRY",
        {"semgrep": SimpleNamespace(adapter_factory=RecordingSemgrep)},
    )
    stage = ScanExecutionStage(
        r2=SimpleNamespace(), api_base_url="http://api", worker_credential="c", runtime=SimpleNamespace()
    )
    stage._create_scanner_run = AsyncMock(return_value=None)
    await stage.run_scanners(context, "scan.repo.full")


@pytest.mark.asyncio
async def test_shadow_pr_run_on_a_fastapi_repository_activates_and_records_the_pack(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text(FASTAPI_SOURCE)
    context = _context(tmp_path, pull_request_number=7)

    await _run(monkeypatch, context)

    assert [record["id"] for record in context.review_packs] == [PACK_ID]
    assert context.review_packs[0]["version"] == PACK_VERSION
    assert RecordingSemgrep.instances[0].review_pack_rules == [PACK_RULES]


@pytest.mark.asyncio
async def test_branch_scans_never_activate_packs(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text(FASTAPI_SOURCE)
    context = _context(tmp_path, pull_request_number=None)

    await _run(monkeypatch, context)

    assert context.review_packs == []
    assert RecordingSemgrep.instances[0].review_pack_rules == []


@pytest.mark.asyncio
async def test_shadow_pr_run_on_a_non_fastapi_repository_activates_nothing(monkeypatch, tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n")
    context = _context(tmp_path, pull_request_number=7)

    await _run(monkeypatch, context)

    assert context.review_packs == []
    assert RecordingSemgrep.instances[0].review_pack_rules == []


def test_semgrep_contained_arguments_add_pack_rules_from_the_scanner_image(monkeypatch):
    monkeypatch.delenv("SEMGREP_CONTAINER_RULES_PATH", raising=False)
    adapter = SemgrepAdapter()
    baseline = adapter.runtime_arguments()
    adapter.review_pack_rules = [PACK_RULES]

    arguments = adapter.runtime_arguments()

    configs = [arguments[i + 1] for i, value in enumerate(arguments) if value == "--config"]
    assert configs == ["/opt/scanner-rules/semgrep-rules.yml", CONTAINER_PACK_RULES]
    assert list(arguments).count("--config") == 2
    pack_index = arguments.index(CONTAINER_PACK_RULES)
    assert arguments[:pack_index - 1] + arguments[pack_index + 1:] == baseline


def test_pack_rules_change_the_semgrep_rules_digest_deterministically(monkeypatch):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", "/nonexistent")
    plain = SemgrepAdapter()
    packed = SemgrepAdapter()
    packed.review_pack_rules = [PACK_RULES]
    again = SemgrepAdapter()
    again.review_pack_rules = [PACK_RULES]

    plain_digest = plain.resolve_provenance()["rules_digest"]
    packed_digest = packed.resolve_provenance()["rules_digest"]

    assert packed_digest != plain_digest
    assert packed_digest == again.resolve_provenance()["rules_digest"]
    pack_digest = "sha256:" + hashlib.sha256(RULES_PATH.read_bytes()).hexdigest()
    assert pack_digest not in (plain_digest, packed_digest)


def _record() -> dict:
    return {"id": PACK_ID, "version": PACK_VERSION, "rules_digest": "sha256:x", "evidence": ["a.py"], "context": []}


def test_completion_summary_records_the_pack_version(tmp_path):
    context = _context(tmp_path, pull_request_number=7)
    context.review_packs = [_record()]

    summary = ScanOrchestrator(queue=SimpleNamespace(), r2=SimpleNamespace())._build_completion_summary(
        context, job_type="scan.repo.full", duration_seconds=1.0
    )

    assert summary["review_packs"] == [_record()]


def test_completion_summary_omits_review_packs_when_none_ran(tmp_path):
    summary = ScanOrchestrator(queue=SimpleNamespace(), r2=SimpleNamespace())._build_completion_summary(
        _context(tmp_path, pull_request_number=None), job_type="scan.repo.full", duration_seconds=1.0
    )

    assert "review_packs" not in summary


@pytest.mark.asyncio
async def test_semgrep_run_metadata_carries_the_pack_version(monkeypatch, tmp_path):
    posted: dict = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        async def post(self, url, json=None, headers=None, timeout=None):
            posted.update(json)
            return SimpleNamespace(raise_for_status=lambda: None)

    monkeypatch.setattr("app.services.scan_pipeline.persistence.httpx.AsyncClient", FakeClient)
    context = _context(tmp_path, pull_request_number=7)
    context.attempt_id = "attempt"
    context.execution_revision = 1
    context.worker_incarnation_id = "inc"
    context.review_packs = [_record()]
    context.scanner_results = {
        "semgrep": ScannerResult(scanner_name="semgrep", success=True, raw_output={}),
        "gitleaks": ScannerResult(scanner_name="gitleaks", success=True, raw_output={}),
    }

    await PersistenceStage("http://api", "c").complete_scan(context)

    runs = {run["scanner_name"]: run for run in posted["scanner_runs"]}
    assert runs["semgrep"]["metadata_json"]["review_packs"] == [
        {"id": PACK_ID, "version": PACK_VERSION, "rules_digest": "sha256:x"}
    ]
    assert "review_packs" not in runs["gitleaks"]["metadata_json"]
