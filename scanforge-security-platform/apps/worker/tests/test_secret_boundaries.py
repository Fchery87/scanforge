import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.normalizers.gitleaks import normalize_gitleaks_output
from app.normalizers.trivy import normalize_trivy_output
from app.scanners.base import ScannerResult
from app.scanners.gitleaks import GitleaksAdapter
from app.security.secret_evidence import (
    assert_ai_disabled_for_private_beta,
    safe_artifact_key,
    sanitize_trivy_output,
)
from app.services.scan_pipeline.context import ScanContext
from app.services.scan_pipeline.execution import ScanExecutionStage

CANARY = "ghp_private_canary_value_123456789"


def test_gitleaks_normalizer_does_not_emit_secret_value():
    findings = normalize_gitleaks_output(
        [{"RuleID": "github_token", "File": "config.py", "StartLine": 4, "Match": CANARY}],
        "repo-1",
    )
    serialized = json.dumps(findings)
    assert CANARY not in serialized
    assert findings[0]["instance"] == {
        "path": "config.py",
        "line_start": 4,
        "line_end": 4,
        "commit": None,
    }


def test_trivy_secret_output_preserves_location_but_removes_value():
    sanitized = sanitize_trivy_output(
        {"Results": [{"Secrets": [{"RuleID": "generic", "File": "config.py", "StartLine": 4, "Match": CANARY}]}]}
    )
    serialized = json.dumps(sanitized)
    assert CANARY not in serialized
    assert sanitized["Results"][0]["Secrets"] == [{"rule_id": "generic", "path": "config.py", "line_start": 4}]


def test_trivy_normalizer_does_not_emit_secret_value():
    findings = normalize_trivy_output(
        {"Results": [{"Secrets": [{"RuleID": "generic", "File": "config.py", "StartLine": 4, "Match": CANARY}]}]},
        "repo-1",
    )
    assert CANARY not in json.dumps(findings)


def test_artifact_key_is_org_scoped_and_rejects_traversal():
    assert safe_artifact_key("org-1", "scan-1", "trivy", "results.json") == (
        "scan-artifacts/org-1/scan-1/trivy/results.json"
    )
    with pytest.raises(ValueError):
        safe_artifact_key("org-1", "scan-1", "trivy", "../secret.json")


def test_private_beta_rejects_ai(monkeypatch):
    monkeypatch.setenv("APP_ENV", "private-beta")
    monkeypatch.setenv("AI_ENABLED", "true")
    with pytest.raises(RuntimeError, match="must remain disabled"):
        assert_ai_disabled_for_private_beta()


def test_gitleaks_temp_report_is_deleted(monkeypatch, tmp_path: Path):
    report = tmp_path / ".gitleaks-report.json"

    def fake_run(*_args, **_kwargs):
        report.write_text(json.dumps([{"RuleID": "generic", "File": "x", "StartLine": 1, "Match": CANARY}]))
        return subprocess.CompletedProcess([], 1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(GitleaksAdapter, "get_version", lambda _self: "1.0.0")

    result = GitleaksAdapter().run(tmp_path)

    assert CANARY in json.dumps(result.raw_output)
    assert result.artifact_paths == []
    assert not report.exists()


@pytest.mark.asyncio
async def test_gitleaks_raw_output_never_reaches_artifact_client(tmp_path):
    r2 = SimpleNamespace(
        upload_raw_output=AsyncMock(),
        upload_file=AsyncMock(),
    )
    stage = ScanExecutionStage(
        r2=r2,
        api_base_url="http://api",
        worker_credential="credential",
        runtime=SimpleNamespace(),
    )
    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha=None,
        job_id="scan-1",
    )
    context.scanner_results = {
        "gitleaks": ScannerResult(
            scanner_name="gitleaks",
            success=True,
            raw_output=[{"Match": CANARY}],
            artifact_paths=[],
        )
    }

    result = await stage.upload_artifacts(context)

    assert CANARY not in json.dumps(result)
    r2.upload_raw_output.assert_not_awaited()
    r2.upload_file.assert_not_awaited()
