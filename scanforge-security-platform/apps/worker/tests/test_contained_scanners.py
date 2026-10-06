import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.runtime.models import ScanRuntimeResult
from app.scanners.base import ScannerAdapter
from app.scanners.registry import SCANNER_REGISTRY
from app.services.scan_pipeline.context import ScanContext
from app.services.scan_pipeline.execution import ScanExecutionStage
from app.services.scan_pipeline.normalization import NormalizationStage

REPORTS = {
    "trivy": {
        "Results": [
            {
                "Target": "requirements.txt",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2026-1234",
                        "PkgName": "requests",
                        "InstalledVersion": "2.0",
                        "Severity": "HIGH",
                    }
                ],
            }
        ]
    },
    "gitleaks": [
        {
            "RuleID": "test-key",
            "File": "config.py",
            "StartLine": 2,
            "EndLine": 2,
            "Secret": "synthetic-canary-secret",
            "Match": "synthetic-canary-secret",
        }
    ],
    "osv": {
        "results": [
            {
                "packages": [
                    {
                        "package": {"name": "requests", "ecosystem": "PyPI", "version": "2.0"},
                        "vulnerabilities": [{"id": "GHSA-test", "summary": "test"}],
                    }
                ]
            }
        ]
    },
    "semgrep": {
        "results": [
            {
                "check_id": "test-rule",
                "path": "source.py",
                "start": {"line": 1},
                "end": {"line": 1},
                "extra": {"message": "Unsafe operation", "severity": "ERROR"},
            }
        ],
        "errors": [],
    },
    "syft": {
        "artifacts": [
            {
                "name": "requests",
                "version": "2.0",
                "type": "python",
                "licenses": [{"value": "GPL-3.0"}],
                "locations": [{"path": "requirements.txt"}],
            }
        ]
    },
    "checkov": [
        {
            "check_type": "terraform",
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_AWS_20",
                        "check_name": "Unsafe bucket",
                        "file_path": "/main.tf",
                        "file_line_range": [1, 3],
                        "resource": "aws_s3_bucket.example",
                    }
                ],
                "parsing_errors": [],
            },
        }
    ],
    "grype": {
        "matches": [
            {
                "artifact": {"name": "requests", "version": "2.0", "type": "python", "locations": []},
                "vulnerability": {"id": "CVE-2026-1234", "severity": "High"},
            }
        ]
    },
}
CLEAN_REPORTS = {
    "trivy": {"Results": []},
    "gitleaks": [],
    "osv": {"results": []},
    "semgrep": {"results": [], "errors": []},
    "syft": {"artifacts": []},
    "checkov": {"results": {"failed_checks": [], "parsing_errors": []}},
    "grype": {"matches": []},
}


class ReportRuntime:
    def __init__(self, name, payload, exit_code=0):
        self.name = name
        self.payload = payload
        self.exit_code = exit_code
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        output = json.dumps(self.payload)
        if self.name == "checkov":
            stdout = output
        else:
            (request.output_directory / f"{self.name}-results.json").write_text(output)
            stdout = ""
        return ScanRuntimeResult(self.exit_code, stdout, "", 1)


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
def test_contained_scanner_executes_source_scan_and_retains_valid_report(name, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    adapter = SCANNER_REGISTRY[name].adapter_factory()
    runtime = ReportRuntime(name, REPORTS[name], 1 if name in {"gitleaks", "osv", "checkov"} else 0)

    result = adapter.run_contained(source, runtime, output)

    assert result.success is True
    assert any("/workspace/source" in value for value in runtime.requests[0].arguments)
    assert runtime.requests[0].arguments != ("--version",)
    assert result.raw_output == REPORTS[name]
    assert all(path.exists() for path in result.artifact_paths)
    if name == "gitleaks":
        assert result.artifact_paths == []
    else:
        assert len(result.artifact_paths) == 1


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
def test_valid_empty_report_is_clean_evidence(name, tmp_path):
    result = (
        SCANNER_REGISTRY[name]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime(name, CLEAN_REPORTS[name]), tmp_path / "output")
    )
    assert result.success is True
    assert result.raw_output == CLEAN_REPORTS[name]


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
@pytest.mark.parametrize("payload", [{}, {"unexpected": []}, "wrong-root"])
def test_incompatible_reports_fail_closed(name, payload, tmp_path):
    result = (
        SCANNER_REGISTRY[name]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime(name, payload), tmp_path / "output")
    )
    assert result.success is False
    assert result.artifact_paths == []


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
def test_fatal_exit_with_valid_output_fails(name, tmp_path):
    result = (
        SCANNER_REGISTRY[name]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime(name, REPORTS[name], 2), tmp_path / "output")
    )
    assert result.success is False
    assert result.artifact_paths == []


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
def test_missing_report_fails(name, tmp_path):
    runtime = SimpleNamespace(run=lambda request: ScanRuntimeResult(0, "", "", 1))
    result = SCANNER_REGISTRY[name].adapter_factory().run_contained(tmp_path, runtime, tmp_path / "output")
    assert result.success is False


@pytest.mark.parametrize("name", ["trivy", "gitleaks", "osv", "semgrep", "syft", "grype"])
def test_report_symlink_is_rejected(name, tmp_path):
    secret = tmp_path / "outside.json"
    secret.write_text(json.dumps(REPORTS[name]))

    def run(request):
        (request.output_directory / f"{name}-results.json").symlink_to(secret)
        return ScanRuntimeResult(0, "", "", 1)

    result = (
        SCANNER_REGISTRY[name].adapter_factory().run_contained(tmp_path, SimpleNamespace(run=run), tmp_path / "output")
    )
    assert result.success is False
    assert result.raw_output == {}


def test_checkov_framework_reports_normalize_real_failed_checks():
    findings = SCANNER_REGISTRY["checkov"].normalize(REPORTS["checkov"], "repo")
    assert len(findings) == 1
    assert findings[0]["instance"]["check_id"] == "CKV_AWS_20"
    assert findings[0]["instance"]["path"] == "main.tf"


@pytest.mark.asyncio
async def test_secret_canary_normalizes_before_upload_and_never_reaches_storage(tmp_path):
    context = ScanContext("scan", "org", "repo", "project", "main", None, "job", repo_path=tmp_path)
    output = tmp_path / "output"
    result = (
        SCANNER_REGISTRY["gitleaks"]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime("gitleaks", REPORTS["gitleaks"], 1), output)
    )
    context.scanner_results = {"gitleaks": result}
    context.findings = NormalizationStage().normalize_results(context)
    r2 = SimpleNamespace(upload_raw_output=AsyncMock(), upload_file=AsyncMock())
    stage = ScanExecutionStage(r2, "http://api", "credential", runtime=SimpleNamespace())

    await stage.upload_artifacts(context)

    assert len(context.findings) == 1
    assert context.findings[0]["category"] == "secret"
    assert "synthetic-canary-secret" not in json.dumps(context.findings)
    r2.upload_raw_output.assert_not_awaited()
    r2.upload_file.assert_not_awaited()
    assert result.raw_output == {}


def test_base_adapter_has_no_successful_contained_default():
    assert "runtime_arguments" in ScannerAdapter.__abstractmethods__
    assert "parse_runtime_result" in ScannerAdapter.__abstractmethods__


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
def test_positive_scanner_report_normalizes_a_finding(name, tmp_path):
    result = (
        SCANNER_REGISTRY[name]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime(name, REPORTS[name]), tmp_path / "output")
    )
    findings = SCANNER_REGISTRY[name].normalize(result.raw_output, "repo")
    assert len(findings) == 1
    assert findings[0]["primary_scanner"] == name
    if name == "osv":
        assert findings[0]["instance"]["installed_version"] == "2.0"


@pytest.mark.parametrize("name", list(SCANNER_REGISTRY))
def test_oversized_report_fails(name, tmp_path):
    adapter = SCANNER_REGISTRY[name].adapter_factory()
    adapter.max_report_bytes = 4
    result = adapter.run_contained(tmp_path, ReportRuntime(name, REPORTS[name]), tmp_path / "output")
    assert result.success is False
    assert result.artifact_paths == []


def test_trivy_accepts_documented_omitted_empty_results(tmp_path):
    payload = {"SchemaVersion": 2, "ArtifactType": "filesystem", "ArtifactName": "/workspace/source"}
    result = (
        SCANNER_REGISTRY["trivy"]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime("trivy", payload), tmp_path / "output")
    )
    assert result.success is True
    assert SCANNER_REGISTRY["trivy"].normalize(result.raw_output, "repo") == []


def test_scanner_parse_error_is_failed_coverage(tmp_path):
    payload = {"results": [], "errors": [{"message": "Parse failed"}]}
    result = (
        SCANNER_REGISTRY["semgrep"]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime("semgrep", payload), tmp_path / "output")
    )
    assert result.success is False


@pytest.mark.asyncio
@pytest.mark.parametrize("storage_failure", [False, True])
async def test_pipeline_retains_artifact_until_upload_and_cleans_every_exit(storage_failure, tmp_path):
    from app.clients.queue import QueueJob
    from app.services.scan_orchestrator import ScanOrchestrator

    repository = tmp_path / "repository"
    repository.mkdir()
    workspace = tmp_path / "workspace"
    context = ScanContext("scan", "org", "repo", "project", "main", None, "job", repo_path=repository)
    context.output_root = workspace
    scanner = SCANNER_REGISTRY["trivy"].adapter_factory()
    result = scanner.run_contained(repository, ReportRuntime("trivy", REPORTS["trivy"]), workspace / "trivy")
    context.scanner_results = {"trivy": result}
    queue = SimpleNamespace(
        update_job_status=AsyncMock(),
        ack=AsyncMock(),
        increment_retry=AsyncMock(return_value=1),
        requeue=AsyncMock(),
        move_to_dlq=AsyncMock(),
    )
    calls = []

    async def upload_file(path, key, **kwargs):
        assert result.artifact_paths[0].exists()
        assert len(context.findings) == 1
        calls.append("upload")
        if storage_failure:
            raise RuntimeError("storage outage")
        return {"storage_uri": "s3://bucket/artifact.json"}

    r2 = SimpleNamespace(
        upload_raw_output=AsyncMock(),
        upload_file=upload_file,
    )
    orchestrator = ScanOrchestrator(queue, r2, runtime=SimpleNamespace())
    orchestrator._load_scan_context = AsyncMock(return_value=context)
    orchestrator._update_scan_status = AsyncMock()
    orchestrator._is_canceled = AsyncMock(return_value=False)
    orchestrator._execution.prepare_repository = AsyncMock(return_value=repository)
    orchestrator._execution.run_scanners = AsyncMock(return_value=context.scanner_results)
    orchestrator._persistence.complete_scan = AsyncMock()
    orchestrator._persistence.send_notifications = AsyncMock()
    orchestrator._ai_investigation.run = AsyncMock()

    success = await orchestrator.process_job(QueueJob.create("scan.repo.full", {"scan_id": "scan"}))

    assert success is not storage_failure
    assert calls == ["upload"]
    r2.upload_raw_output.assert_not_awaited()
    assert not workspace.exists()
    assert not repository.exists()
    if storage_failure:
        orchestrator._persistence.complete_scan.assert_not_awaited()
        queue.ack.assert_not_awaited()
        queue.requeue.assert_awaited_once()
    else:
        orchestrator._persistence.complete_scan.assert_awaited_once()
        queue.ack.assert_awaited_once()


def test_image_manifest_requires_supported_versions_and_every_offline_asset():
    from app.scanners.image_manifest import ASSET_PATHS, SUPPORTED_SCANNER_VERSIONS, validate_manifest

    manifest = {
        "schema_version": 1,
        "scanners": dict(SUPPORTED_SCANNER_VERSIONS),
        "assets": {name: {"path": path, "sha256": "a" * 64} for name, path in ASSET_PATHS.items()},
    }
    assert validate_manifest(manifest) == manifest
    manifest["scanners"]["osv"] = "1.0.0"
    with pytest.raises(ValueError, match="unsupported scanner versions"):
        validate_manifest(manifest)
    manifest["scanners"]["osv"] = SUPPORTED_SCANNER_VERSIONS["osv"]
    del manifest["assets"]["osv-db"]
    with pytest.raises(ValueError, match="incomplete offline assets"):
        validate_manifest(manifest)


@pytest.mark.asyncio
async def test_trivy_canary_keeps_rule_location_and_uploads_only_sanitized_evidence(tmp_path):
    payload = {
        "Results": [
            {
                "Target": "config.py",
                "Secrets": [
                    {
                        "RuleID": "test-token",
                        "File": "config.py",
                        "StartLine": 7,
                        "Secret": "synthetic-trivy-canary",
                        "Match": "synthetic-trivy-canary",
                    }
                ],
            }
        ]
    }
    result = (
        SCANNER_REGISTRY["trivy"]
        .adapter_factory()
        .run_contained(tmp_path, ReportRuntime("trivy", payload), tmp_path / "trivy")
    )
    context = ScanContext("scan", "org", "repo", "project", "main", None, "job", repo_path=tmp_path)
    context.scanner_results = {"trivy": result}
    context.findings = NormalizationStage().normalize_results(context)
    captures = []

    async def upload_raw_output(**kwargs):
        captures.append(json.dumps(kwargs["output_data"]))
        return "s3://bucket/raw.json"

    async def upload_file(path, key, **kwargs):
        captures.append(path.read_text())
        return {"storage_uri": "s3://bucket/artifact.json"}

    stage = ScanExecutionStage(
        SimpleNamespace(upload_raw_output=upload_raw_output, upload_file=upload_file),
        "http://api",
        "credential",
        runtime=SimpleNamespace(),
    )
    await stage.upload_artifacts(context)

    assert len(context.findings) == 1
    assert context.findings[0]["instance"] == {"path": "config.py", "line_start": 7, "rule_id": "test-token"}
    assert "synthetic-trivy-canary" not in json.dumps(context.findings)
    assert len(captures) == 1
    assert all("synthetic-trivy-canary" not in value for value in captures)
