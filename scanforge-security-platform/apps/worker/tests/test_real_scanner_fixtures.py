"""Task M05 verification: real scanner execution, parser outcomes, provenance, and secret boundaries.

Exercises all seven shipped scanners (trivy, gitleaks, osv, semgrep, syft,
checkov, grype) against:
1. Contained positive, empty, malformed, truncated, and timeout reports.
2. Image manifest provenance and 7-day database freshness rules.
3. Real pinned scanner executables on positive and empty repository fixtures,
   verifying canary secret non-leakage across findings and uploaded artifacts.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import zipfile

import pytest

from app.runtime.models import ScanRuntimeResult
from app.scanners.registry import SCANNER_REGISTRY
from app.services.scan_pipeline.context import ScanContext
from app.services.scan_pipeline.execution import ScanExecutionStage
from app.services.scan_pipeline.normalization import NormalizationStage

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "scanners"
MANIFEST_FIXTURE_PATH = FIXTURES_DIR / "manifest.json"
POSITIVE_REPORTS_PATH = FIXTURES_DIR / "positive_reports.json"

# Dynamically assembled canary token so static scanners do not flag source files
CANARY_SECRET = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"

EMPTY_REPORTS: dict[str, dict | list] = {
    "trivy": {"SchemaVersion": 2, "Results": []},
    "gitleaks": [],
    "osv": {"results": []},
    "semgrep": {"results": []},
    "syft": {"artifacts": []},
    "checkov": {"results": {"failed_checks": []}},
    "grype": {"matches": []},
}

OUTPUT_FILENAMES: dict[str, str] = {
    "trivy": "trivy-results.json",
    "gitleaks": "gitleaks-report.json",
    "osv": "osv-results.json",
    "semgrep": "semgrep-results.json",
    "syft": "syft-results.json",
    "checkov": "checkov-results.json",
    "grype": "grype-results.json",
}


def _load_positive_reports_with_canary() -> dict[str, dict | list]:
    raw = json.loads(POSITIVE_REPORTS_PATH.read_text())
    injected = copy.deepcopy(raw)
    injected["trivy"]["Results"][1]["Secrets"][0]["Match"] = CANARY_SECRET
    injected["gitleaks"][0]["Match"] = CANARY_SECRET
    injected["gitleaks"][0]["Secret"] = CANARY_SECRET
    injected["semgrep"]["results"][0]["extra"]["lines"] = f'GITHUB_TOKEN = "{CANARY_SECRET}"'
    injected["semgrep"]["results"][0]["extra"]["message"] = f"Detected token {CANARY_SECRET}"
    return injected


@pytest.mark.parametrize(
    "scanner_name",
    ["trivy", "gitleaks", "osv", "semgrep", "syft", "checkov", "grype"],
)
def test_contained_scanner_positive_empty_malformed_truncated_and_timeout_outcomes(
    monkeypatch,
    tmp_path: Path,
    scanner_name: str,
):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST_FIXTURE_PATH))
    positive_reports = _load_positive_reports_with_canary()
    registration = SCANNER_REGISTRY[scanner_name]
    adapter = registration.adapter_factory()
    output_filename = OUTPUT_FILENAMES[scanner_name]

    # 1. Positive report
    class _PositiveRuntime:
        def run(self, request):
            assert request.executable == adapter.binary_name
            assert "--version" not in request.arguments
            payload_str = json.dumps(positive_reports[scanner_name])
            if scanner_name == "checkov":
                return ScanRuntimeResult(
                    exit_code=1,
                    stdout=payload_str,
                    stderr="",
                    duration_ms=42,
                    timed_out=False,
                )
            (request.output_directory / output_filename).write_text(payload_str)
            return ScanRuntimeResult(
                exit_code=1 if scanner_name in {"gitleaks", "osv"} else 0,
                stdout="",
                stderr="",
                duration_ms=42,
                timed_out=False,
            )

    pos_result = adapter.run_contained(tmp_path, _PositiveRuntime())
    assert pos_result.success is True
    assert pos_result.outcome_status == "completed"
    assert pos_result.version
    assert pos_result.parser_version == "2026-10-parser.v1"

    if scanner_name == "gitleaks":
        assert pos_result.artifact_paths == []
        assert pos_result.output_directory is None
    else:
        assert len(pos_result.artifact_paths) == 1
        assert pos_result.artifact_paths[0].exists()
        assert CANARY_SECRET not in pos_result.artifact_paths[0].read_text()

    normalized = registration.normalize(pos_result.raw_output, "repo-1")
    assert len(normalized) >= 1
    assert CANARY_SECRET not in json.dumps(normalized)

    # Clean up retained output directory after verification
    if pos_result.output_directory and pos_result.output_directory.exists():
        for p in pos_result.artifact_paths:
            p.unlink(missing_ok=True)
        pos_result.output_directory.rmdir()

    # 2. Empty report
    class _EmptyRuntime:
        def run(self, request):
            if scanner_name == "osv":
                return ScanRuntimeResult(
                    exit_code=128,
                    stdout="",
                    stderr="No package sources found, --help for usage information.",
                    duration_ms=15,
                    timed_out=False,
                )
            payload_str = json.dumps(EMPTY_REPORTS[scanner_name])
            if scanner_name == "checkov":
                return ScanRuntimeResult(
                    exit_code=0,
                    stdout=payload_str,
                    stderr="",
                    duration_ms=15,
                    timed_out=False,
                )
            (request.output_directory / output_filename).write_text(payload_str)
            return ScanRuntimeResult(
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=15,
                timed_out=False,
            )

    emp_result = adapter.run_contained(tmp_path, _EmptyRuntime())
    assert emp_result.success is True
    assert emp_result.outcome_status == "completed"
    assert registration.normalize(emp_result.raw_output, "repo-1") == []
    if emp_result.output_directory and emp_result.output_directory.exists():
        for p in emp_result.artifact_paths:
            p.unlink(missing_ok=True)
        emp_result.output_directory.rmdir()

    # 3. Malformed report
    class _MalformedRuntime:
        def run(self, request):
            bad_json = "<<<not-valid-json>>>"
            if scanner_name == "checkov":
                return ScanRuntimeResult(
                    exit_code=0,
                    stdout=bad_json,
                    stderr="",
                    duration_ms=10,
                    timed_out=False,
                )
            (request.output_directory / output_filename).write_text(bad_json)
            return ScanRuntimeResult(
                exit_code=1 if scanner_name == "gitleaks" else 0,
                stdout="",
                stderr="",
                duration_ms=10,
                timed_out=False,
            )

    mal_result = adapter.run_contained(tmp_path, _MalformedRuntime())
    assert mal_result.success is False
    assert mal_result.outcome_status == "invalid_output"
    assert mal_result.artifact_paths == []

    # 4. Truncated report
    class _TruncatedRuntime:
        def run(self, request):
            full_str = json.dumps(positive_reports[scanner_name])
            truncated_str = full_str[: max(5, len(full_str) // 2)]
            if scanner_name == "checkov":
                return ScanRuntimeResult(
                    exit_code=1,
                    stdout=truncated_str,
                    stderr="",
                    duration_ms=10,
                    timed_out=False,
                )
            (request.output_directory / output_filename).write_text(truncated_str)
            return ScanRuntimeResult(
                exit_code=1,
                stdout="",
                stderr="",
                duration_ms=10,
                timed_out=False,
            )

    trunc_result = adapter.run_contained(tmp_path, _TruncatedRuntime())
    assert trunc_result.success is False
    assert trunc_result.outcome_status == "invalid_output"
    assert trunc_result.artifact_paths == []

    # 5. Timeout report
    class _TimeoutRuntime:
        def run(self, request):
            return ScanRuntimeResult(
                exit_code=-9,
                stdout="",
                stderr="timed out",
                duration_ms=600_000,
                timed_out=True,
            )

    timeout_result = adapter.run_contained(tmp_path, _TimeoutRuntime())
    assert timeout_result.success is False
    assert timeout_result.outcome_status == "timed_out"
    assert timeout_result.artifact_paths == []


def test_manifest_provenance_and_db_freshness_enforcement(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST_FIXTURE_PATH))

    fresh_now = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
    stale_now = datetime(2026, 10, 25, 12, 0, 0, tzinfo=UTC)

    for name in ("trivy", "grype", "osv"):
        adapter = SCANNER_REGISTRY[name].adapter_factory()
        fresh_prov = adapter.resolve_provenance(now=fresh_now)
        assert fresh_prov["db_freshness_state"] == "fresh"
        assert fresh_prov["db_digest"] is not None
        assert fresh_prov["image_digest"].startswith("sha256:")

        stale_prov = adapter.resolve_provenance(now=stale_now)
        assert stale_prov["db_freshness_state"] == "stale"

    for name in ("gitleaks", "semgrep", "syft", "checkov"):
        adapter = SCANNER_REGISTRY[name].adapter_factory()
        prov = adapter.resolve_provenance(now=stale_now)
        assert prov["db_freshness_state"] == "not_applicable"


@pytest.mark.asyncio
async def test_real_pinned_scanner_executables_positive_and_empty_fixtures(
    monkeypatch,
    tmp_path: Path,
):
    """Execute all 7 real scanner binaries installed on the host against positive and empty repos."""
    monkeypatch.setenv(
        "PATH",
        f"/home/nochaserz/.local/bin:/home/nochaserz/go/bin:{Path('/usr/bin')}:{Path('/bin')}",
    )
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST_FIXTURE_PATH))
    monkeypatch.setenv("CHECKOV_FRAMEWORKS", "terraform")
    monkeypatch.setenv("CHECKOV_CHECKS", "CKV_AWS_20")

    # Set up offline OSV database for PyPI requests==2.19.0 so osv-scanner runs with zero network
    osv_db_dir = tmp_path / "osv_db"
    pypi_db = osv_db_dir / "osv-scanner" / "PyPI"
    pypi_db.mkdir(parents=True)
    with zipfile.ZipFile(pypi_db / "all.zip", "w") as zf:
        zf.writestr(
            "CVE-2023-32681.json",
            json.dumps(
                {
                    "schema_version": "1.6.0",
                    "id": "CVE-2023-32681",
                    "modified": "2026-10-15T00:00:00Z",
                    "published": "2026-10-15T00:00:00Z",
                    "summary": "Unintended leak of Proxy-Authorization header in requests",
                    "severity": [
                        {
                            "type": "CVSS_V3",
                            "score": "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:N/A:N",
                        }
                    ],
                    "affected": [
                        {
                            "package": {"ecosystem": "PyPI", "name": "requests"},
                            "ranges": [
                                {
                                    "type": "ECOSYSTEM",
                                    "events": [{"introduced": "0"}, {"fixed": "2.31.0"}],
                                }
                            ],
                            "versions": ["2.19.0"],
                        }
                    ],
                }
            ),
        )
    monkeypatch.setenv("OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY", str(osv_db_dir))

    pos_repo = tmp_path / "positive_repo"
    pos_repo.mkdir()
    (pos_repo / "requirements.txt").write_text("requests==2.19.0\n")
    (pos_repo / "main.tf").write_text(
        'resource "aws_s3_bucket" "public_bucket" {\n'
        '  bucket = "scanforge-fixture-bucket"\n'
        '  acl    = "public-read"\n'
        "}\n"
    )
    (pos_repo / "app.py").write_text(
        "import subprocess\n"
        f'GITHUB_TOKEN = "{CANARY_SECRET}"\n'
        'subprocess.run("echo hello", shell=True)\n'
    )

    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    (empty_repo / "README.md").write_text("# Clean Repository\n")

    pos_results = {}
    for name, registration in SCANNER_REGISTRY.items():
        adapter = registration.adapter_factory()
        res = adapter.run(pos_repo)
        assert res.success is True, f"{name} failed on positive repo: {res.error}"
        assert res.outcome_status == "completed"
        findings = registration.normalize(res.raw_output, "repo-pos")
        assert len(findings) >= 1, f"{name} produced 0 normalized findings on positive repo"
        pos_results[name] = res

        emp_res = adapter.run(empty_repo)
        assert emp_res.success is True, f"{name} failed on empty repo: {emp_res.error}"
        assert emp_res.outcome_status == "completed"
        emp_findings = registration.normalize(emp_res.raw_output, "repo-empty")
        assert emp_findings == [], f"{name} produced unexpected findings on empty repo: {emp_findings}"

    # Verify full pipeline normalization + upload + cleanup with canary inspection
    uploaded_blobs: list[str] = []

    async def _upload_raw(**kwargs):
        blob = json.dumps(kwargs["output_data"])
        uploaded_blobs.append(blob)
        return f"r2://bucket/{kwargs['scanner_name']}/raw.json"

    async def _upload_file(path: Path, key: str):
        uploaded_blobs.append(path.read_text())
        return {"storage_uri": f"r2://bucket/{key}"}

    r2 = SimpleNamespace(
        upload_raw_output=AsyncMock(side_effect=_upload_raw),
        upload_file=AsyncMock(side_effect=_upload_file),
    )
    exec_stage = ScanExecutionStage(
        r2=r2,
        api_base_url="http://api.local",
        worker_credential="worker-secret-cred",
        runtime=SimpleNamespace(),
    )
    norm_stage = NormalizationStage()
    context = ScanContext(
        scan_id="scan-pos-1",
        organization_id="org-1",
        repository_id="repo-pos",
        project_id="proj-1",
        branch="main",
        commit_sha="a" * 40,
        job_id="job-pos-1",
        repo_path=pos_repo,
        scanner_results=pos_results,
    )

    reconciled_findings = norm_stage.normalize_results(context)
    artifact_uris = await exec_stage.upload_artifacts(context)
    exec_stage.cleanup_scanner_artifacts(context)

    assert len(reconciled_findings) >= 4
    categories = {f["category"] for f in reconciled_findings}
    assert {"secret", "vulnerability", "iac_misconfiguration", "license_compliance"} <= categories
    assert CANARY_SECRET not in json.dumps(reconciled_findings)
    assert CANARY_SECRET not in json.dumps(artifact_uris)
    for blob in uploaded_blobs:
        assert CANARY_SECRET not in blob
    for res in context.scanner_results.values():
        assert res.artifact_paths == []
