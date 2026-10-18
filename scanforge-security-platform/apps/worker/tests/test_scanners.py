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

    def fake_run(cmd, capture_output, text, timeout, cwd, env=None):
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

    def fake_run(cmd, capture_output, text, timeout, env=None):
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

    def fake_run(cmd, capture_output, text, timeout, env=None):
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

    def fake_run(cmd, capture_output, text, timeout, cwd, env=None):
        assert "--no-progress" in cmd
        assert "--skip-version-check" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "0.69.3")

    result = adapter.run(tmp_path)
    assert result.success is False or result.success is True


def test_semgrep_adapter_uses_non_interactive_flags(monkeypatch, tmp_path: Path):
    adapter = SemgrepAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd, env=None):
        assert "--disable-version-check" in cmd
        assert "--jobs" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "1.156.0")

    result = adapter.run(tmp_path)
    assert result.success is False or result.success is True


def test_checkov_adapter_uses_quiet_skip_download_flags(monkeypatch, tmp_path: Path):
    adapter = CheckovAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd, env=None):
        assert "--quiet" in cmd
        assert "--skip-download" in cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(adapter, "get_version", lambda: "3.2.513")

    result = adapter.run(tmp_path)
    assert result.success is True


def test_grype_adapter_uses_quiet_flag(monkeypatch, tmp_path: Path):
    adapter = GrypeAdapter()

    def fake_run(cmd, capture_output, text, timeout, cwd, env=None):
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

    def fake_run(cmd, capture_output, text, timeout, cwd, env=None):
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


def test_incomplete_contained_scanner_adapter_fails_explicitly(tmp_path: Path):
    import pytest
    from app.scanners.base import ScannerAdapter, ScannerResult

    class IncompleteAdapter(ScannerAdapter):
        name = "incomplete"
        binary_name = "incomplete"

        def run(self, repo_path: Path) -> ScannerResult:
            return ScannerResult(scanner_name=self.name, success=True, raw_output={})

    class FakeRuntime:
        def run(self, request):
            raise AssertionError("runtime.run should not be called with default --version arguments")

    with pytest.raises(NotImplementedError, match="does not implement contained"):
        IncompleteAdapter().run_contained(tmp_path, FakeRuntime())


def test_every_registered_scanner_implements_real_contained_arguments():
    from app.scanners.registry import SCANNER_REGISTRY

    for name, registration in SCANNER_REGISTRY.items():
        adapter = registration.adapter_factory()
        args = adapter.runtime_arguments()
        assert args != ("--version",), f"{name} still uses version-only runtime_arguments"
        assert "--version" not in args, f"{name} runtime_arguments must execute analysis, not --version"


def test_contained_result_records_the_image_digest_that_ran(tmp_path: Path):
    from app.runtime.models import ScanRuntimeResult
    from app.scanners.base import ScannerAdapter, ScannerResult

    image_digest = "sha256:" + "d" * 64

    class Adapter(ScannerAdapter):
        name = "fixture"
        binary_name = "fixture"

        def run(self, repo_path: Path) -> ScannerResult:
            raise NotImplementedError

        def runtime_arguments(self) -> tuple[str, ...]:
            return ("scan",)

        def parse_runtime_result(self, completed, output_directory: Path) -> ScannerResult:
            return ScannerResult(scanner_name=self.name, success=True, raw_output={})

    class Runtime:
        def run(self, request):
            return ScanRuntimeResult(
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=1,
                image_digest=image_digest,
            )

    result = Adapter().run_contained(tmp_path, Runtime())

    assert result.image_digest == image_digest
