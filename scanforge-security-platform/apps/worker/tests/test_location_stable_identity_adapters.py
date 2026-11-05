"""P1.5 (#38): snippet digests come from the checked-out source, before sanitization strips snippets."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from app.normalizers.checkov import normalize_checkov_output
from app.normalizers.semgrep import normalize_semgrep_output
from app.runtime.models import ScanRuntimeResult
from app.scanners.checkov import CheckovAdapter
from app.scanners.semgrep import SemgrepAdapter

MANIFEST = Path(__file__).resolve().parent / "fixtures" / "scanners" / "manifest.json"
RULE = "python.lang.security.audit.subprocess-shell-true"
VULN = "subprocess.run(cmd, shell=True)\n"
CANARY = "ghp_" + "Zx9Qw8Er7Ty6Ui5Op4As3Df2Gh1Jk0LmNbVc"


def _semgrep_report(path: str, line: int) -> dict:
    return {
        "results": [
            {
                "check_id": RULE,
                "path": f"/workspace/source/{path}",
                "start": {"line": line, "col": 1},
                "end": {"line": line, "col": 30},
                "extra": {
                    "severity": "ERROR",
                    "message": "shell=True",
                    "lines": "requires login",
                    "metadata": {"category": "security", "confidence": "HIGH"},
                },
            }
        ]
    }


def _semgrep_findings(source: Path, path: str, line: int) -> list[dict]:
    report = _semgrep_report(path, line)

    class _Runtime:
        def run(self, request):
            (request.output_directory / "semgrep-results.json").write_text(json.dumps(report))
            return ScanRuntimeResult(exit_code=1, stdout="", stderr="", duration_ms=1, timed_out=False)

    result = SemgrepAdapter().run_contained(source, _Runtime())
    assert result.success
    for artifact in result.artifact_paths:
        artifact.unlink(missing_ok=True)
    return normalize_semgrep_output(copy.deepcopy(result.raw_output), "repo-1")


def test_semgrep_identity_follows_the_code_not_the_line(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST))
    (tmp_path / "src").mkdir()
    app = tmp_path / "src" / "app.py"

    app.write_text(f"import subprocess\n{VULN}")
    original = _semgrep_findings(tmp_path, "src/app.py", 2)[0]
    app.write_text(f"import subprocess\n\n\n\n  {VULN.strip()}   \n")
    moved = _semgrep_findings(tmp_path, "src/app.py", 5)[0]
    app.write_text("import subprocess\nsubprocess.run(cmd, shell=True, check=True)\n")
    edited = _semgrep_findings(tmp_path, "src/app.py", 2)[0]

    assert original["canonical_fingerprint"] == moved["canonical_fingerprint"]
    assert original["canonical_fingerprint"] != edited["canonical_fingerprint"]
    assert "snippet_unavailable" not in original["metadata_json"]
    assert moved["instance"]["line_start"] == 5


def test_semgrep_snippet_digest_ignores_secret_material(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST))
    app = tmp_path / "app.py"
    app.write_text(f'TOKEN = "{CANARY}"\n')
    first = _semgrep_findings(tmp_path, "app.py", 1)[0]
    app.write_text('TOKEN = "ghp_' + "Qq" * 18 + '"\n')
    second = _semgrep_findings(tmp_path, "app.py", 1)[0]

    assert first["canonical_fingerprint"] == second["canonical_fingerprint"]
    assert CANARY not in json.dumps(first)


def test_semgrep_does_not_read_outside_the_checkout(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST))
    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "outside.py").write_text(VULN)
    (source / "link.py").symlink_to(tmp_path / "outside.py")

    for path in ("../outside.py", "link.py"):
        finding = _semgrep_findings(source, path, 1)[0]
        assert finding["metadata_json"]["snippet_unavailable"] is True


def _checkov_finding(source: Path, lines: list[int]) -> dict:
    report = {
        "results": {
            "failed_checks": [
                {
                    "check_id": "CKV_AWS_20",
                    "check_name": "public READ",
                    "file_path": "/main.tf",
                    "file_line_range": lines,
                    "resource": "aws_s3_bucket.b",
                    "severity": "HIGH",
                    "code_block": [[lines[0], 'resource "aws_s3_bucket" "b" {\n']],
                }
            ]
        }
    }

    class _Runtime:
        def run(self, request):
            return ScanRuntimeResult(exit_code=1, stdout=json.dumps(report), stderr="", duration_ms=1, timed_out=False)

    result = CheckovAdapter().run_contained(source, _Runtime())
    assert result.success
    for artifact in result.artifact_paths:
        artifact.unlink(missing_ok=True)
    return normalize_checkov_output(copy.deepcopy(result.raw_output), "repo-1")[0]


def test_checkov_identity_follows_the_resource_block(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SCANNER_MANIFEST_PATH", str(MANIFEST))
    block = 'resource "aws_s3_bucket" "b" {\n  acl = "public-read"\n}\n'
    tf = tmp_path / "main.tf"

    tf.write_text(block)
    original = _checkov_finding(tmp_path, [1, 3])
    tf.write_text("# header\n\n" + block)
    moved = _checkov_finding(tmp_path, [3, 5])
    tf.write_text("# header\n\n" + block.replace("public-read", "private"))
    edited = _checkov_finding(tmp_path, [3, 5])

    assert original["canonical_fingerprint"] == moved["canonical_fingerprint"]
    assert original["canonical_fingerprint"] != edited["canonical_fingerprint"]
    assert "snippet_unavailable" not in original["metadata_json"]
