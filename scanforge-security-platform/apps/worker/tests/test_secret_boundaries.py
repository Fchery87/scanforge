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


def test_trivy_sanitization_is_idempotent_and_normalizer_preserves_rule_and_location():
    raw = {
        "Results": [
            {
                "Target": "src/config.py",
                "Secrets": [
                    {
                        "RuleID": "github-pat",
                        "Category": "GitHub",
                        "File": "src/config.py",
                        "StartLine": 14,
                        "EndLine": 15,
                        "Commit": "abc1234",
                        "Match": CANARY,
                        "Code": {"Lines": [{"Content": CANARY}]},
                    }
                ],
            }
        ]
    }
    once = sanitize_trivy_output(raw)
    twice = sanitize_trivy_output(once)
    assert once == twice
    assert CANARY not in json.dumps(twice)
    assert twice["Results"][0]["Secrets"] == [
        {
            "rule_id": "github-pat",
            "secret_type": "GitHub",
            "path": "src/config.py",
            "line_start": 14,
            "line_end": 15,
            "commit": "abc1234",
        }
    ]

    findings = normalize_trivy_output(raw, "repo-1")
    assert len(findings) == 1
    assert CANARY not in json.dumps(findings)
    assert findings[0]["category"] == "secret"
    assert findings[0]["title"] == "Exposed secret: github-pat"
    assert findings[0]["instance"]["rule_id"] == "github-pat"
    assert findings[0]["instance"]["path"] == "src/config.py"
    assert findings[0]["instance"]["line_start"] == 14


@pytest.mark.asyncio
async def test_gitleaks_evidence_survives_upload_and_normalization_order():
    from app.services.scan_pipeline.normalization import NormalizationStage

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
    normalization = NormalizationStage()
    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha="a" * 40,
        job_id="scan-1",
    )
    context.scanner_results = {
        "gitleaks": ScannerResult(
            scanner_name="gitleaks",
            success=True,
            raw_output=[
                {
                    "RuleID": "github-pat",
                    "File": "src/config.py",
                    "StartLine": 12,
                    "EndLine": 12,
                    "Commit": "deadbeef",
                    "Match": CANARY,
                    "Secret": CANARY,
                }
            ],
            artifact_paths=[],
        )
    }

    uris = await stage.upload_artifacts(context)
    findings = normalization.normalize_results(context)

    assert len(findings) == 1
    assert findings[0]["category"] == "secret"
    assert findings[0]["instance"]["path"] == "src/config.py"
    assert findings[0]["instance"]["line_start"] == 12
    assert CANARY not in json.dumps(findings)
    assert CANARY not in json.dumps(uris)
    assert CANARY not in json.dumps(context.scanner_results["gitleaks"].raw_output)
    r2.upload_raw_output.assert_not_awaited()
    r2.upload_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_source_bearing_scanner_artifacts_and_findings_scrub_canary(tmp_path: Path):
    from app.services.scan_pipeline.normalization import NormalizationStage

    uploaded_payloads: list[str] = []

    async def capture_raw_output(**kwargs):
        uploaded_payloads.append(json.dumps(kwargs["output_data"]))
        return f"r2://bucket/{kwargs['scanner_name']}/raw.json"

    async def capture_file(path: Path, key: str):
        uploaded_payloads.append(path.read_text())
        return {"storage_uri": f"r2://bucket/{key}"}

    r2 = SimpleNamespace(
        upload_raw_output=AsyncMock(side_effect=capture_raw_output),
        upload_file=AsyncMock(side_effect=capture_file),
    )
    stage = ScanExecutionStage(
        r2=r2,
        api_base_url="http://api",
        worker_credential="credential",
        runtime=SimpleNamespace(),
    )
    semgrep_artifact = tmp_path / "semgrep-results.json"
    semgrep_raw = {
        "results": [
            {
                "check_id": "python.lang.security.audit.hardcoded-token",
                "path": "src/app.py",
                "start": {"line": 8},
                "end": {"line": 8},
                "extra": {
                    "severity": "ERROR",
                    "message": f"Hardcoded token {CANARY} detected",
                    "lines": f'API_TOKEN = "{CANARY}"',
                    "metadata": {"category": "security", "confidence": "HIGH"},
                },
            }
        ]
    }
    semgrep_artifact.write_text(json.dumps(semgrep_raw))

    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha="b" * 40,
        job_id="scan-1",
    )
    context.scanner_results = {
        "semgrep": ScannerResult(
            scanner_name="semgrep",
            success=True,
            raw_output=semgrep_raw,
            artifact_paths=[semgrep_artifact],
        )
    }

    findings = NormalizationStage().normalize_results(context)
    await stage.upload_artifacts(context)

    assert len(findings) == 1
    assert CANARY not in json.dumps(findings)
    assert "lines" not in findings[0]["instance"]
    assert uploaded_payloads
    for payload in uploaded_payloads:
        assert CANARY not in payload
