import json
import subprocess
from pathlib import Path

from app.scanners.syft import SyftAdapter
from app.scanners.trivy import TrivyAdapter
from app.scanners.checkov import CheckovAdapter


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
