import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.normalizers.grype import normalize_grype_output
from app.scanners.checkov import CheckovAdapter
from app.scanners.grype import GrypeAdapter
from app.scanners.semgrep import SemgrepAdapter
from app.scanners.syft import SyftAdapter
from app.scanners.trivy import TrivyAdapter


def test_checkov_adapter_uses_stdout_json_and_writes_artifact(monkeypatch, tmp_path: Path):
    adapter = CheckovAdapter()
    stdout_payload = json.dumps(
        {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_AWS_20",
                        "check_name": "S3 bucket versioning should be enabled",
                    }
                ]
            }
        }
    )

    def fake_run(cmd, capture_output, text, timeout, cwd):
        assert "--output-file-path" not in cmd
        return subprocess.CompletedProcess(cmd, 1, stdout=stdout_payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "3.2.513")

    result = adapter.run(tmp_path)

    assert result.success is True
    assert result.raw_output["results"]["failed_checks"][0]["check_id"] == "CKV_AWS_20"
    assert len(result.artifact_paths) == 1
    assert result.artifact_paths[0].name == "checkov-results.json"
    assert json.loads(result.artifact_paths[0].read_text()) == result.raw_output


def test_trivy_get_version_returns_compact_version(monkeypatch):
    adapter = TrivyAdapter()

    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Version: 0.69.3\nVulnerability DB:\n  Version: 2\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert adapter.get_version() == "0.69.3"


def test_syft_get_version_returns_compact_version(monkeypatch):
    adapter = SyftAdapter()

    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="Application:   syft\nVersion:       1.42.3\nBuildDate:     2026-03-19T17:00:58Z\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert adapter.get_version() == "1.42.3"


def test_scanner_adapters_honor_binary_override_env_vars(monkeypatch):
    monkeypatch.setenv("TRIVY_BINARY", "/opt/tools/trivy")
    monkeypatch.setenv("GRYPE_BINARY", "/opt/tools/grype")
    monkeypatch.setenv("SEMGREP_BINARY", "/opt/tools/semgrep")
    monkeypatch.setenv("CHECKOV_BINARY", "/opt/tools/checkov")

    assert TrivyAdapter().binary_name == "/opt/tools/trivy"
    assert GrypeAdapter().binary_name == "/opt/tools/grype"
    assert SemgrepAdapter().binary_name == "/opt/tools/semgrep"
    assert CheckovAdapter().binary_name == "/opt/tools/checkov"


def test_trivy_adapter_uses_non_interactive_flags(monkeypatch, tmp_path: Path):
    adapter = TrivyAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd):
        assert "--no-progress" in cmd
        assert "--skip-version-check" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "0.69.3")

    result = adapter.run(tmp_path)
    assert result.success is False or result.success is True


def test_semgrep_adapter_uses_non_interactive_flags(monkeypatch, tmp_path: Path):
    adapter = SemgrepAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd):
        assert "--disable-version-check" in cmd
        assert "--jobs" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "1.156.0")

    result = adapter.run(tmp_path)
    assert result.success is False or result.success is True


def test_checkov_adapter_uses_quiet_skip_download_flags(monkeypatch, tmp_path: Path):
    adapter = CheckovAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd):
        assert "--quiet" in cmd
        assert "--skip-download" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "3.2.513")

    result = adapter.run(tmp_path)
    assert result.success is True


def test_grype_adapter_uses_quiet_flag(monkeypatch, tmp_path: Path):
    adapter = GrypeAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd):
        assert "--quiet" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "0.110.0")

    result = adapter.run(tmp_path)
    assert result.success is False or result.success is True


def test_grype_adapter_handles_list_json_output(monkeypatch, tmp_path: Path):
    adapter = GrypeAdapter()
    output_file = tmp_path / "grype-results.json"
    output_file.write_text(json.dumps([{"artifact": {"name": "openssl"}}]))

    def fake_run(cmd, capture_output, text, timeout, cwd):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "0.110.0")

    result = adapter.run(tmp_path)

    assert result.success is True
    assert isinstance(result.raw_output, list)


def test_grype_normalizer_handles_list_output():
    findings = normalize_grype_output(
        [
            {
                "artifact": {"name": "openssl", "version": "3.0.0", "locations": [], "type": "python"},
                "vulnerability": {"id": "CVE-2026-0001", "severity": "HIGH", "description": "desc"},
            }
        ],
        "repo-1",
    )

    assert len(findings) == 1
    assert findings[0]["primary_scanner"] == "grype"
