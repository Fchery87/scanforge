"""P1.5 (#38): source and secret findings keep identity when code moves (fp.v3)."""

from __future__ import annotations

import json

from app.normalizers.checkov import normalize_checkov_output
from app.normalizers.gitleaks import normalize_gitleaks_output
from app.normalizers.semgrep import normalize_semgrep_output

RULE = "python.lang.security.audit.subprocess-shell-true"


def _semgrep_result(line: int, digest: str | None, *, path: str = "/workspace/source/src/app.py") -> dict:
    result = {
        "check_id": RULE,
        "path": path,
        "start": {"line": line, "col": 1},
        "end": {"line": line, "col": 30},
        "extra": {
            "severity": "ERROR",
            "message": "Found subprocess invocation with shell=True",
            "metadata": {"category": "security", "confidence": "HIGH"},
        },
    }
    if digest is not None:
        result["snippet_sha256"] = digest
    return result


def _semgrep(results: list[dict]) -> list[dict]:
    return normalize_semgrep_output({"results": results}, "repo-1")


def test_semgrep_moved_block_keeps_fingerprint_and_declares_fp_v3():
    before = _semgrep([_semgrep_result(10, "a" * 64)])[0]
    after = _semgrep([_semgrep_result(250, "a" * 64)])[0]

    assert before["canonical_fingerprint"] == after["canonical_fingerprint"]
    assert before["fingerprint_version"] == "fp.v3"
    assert before["instance"]["line_start"] == 10
    assert after["instance"]["line_start"] == 250


def test_semgrep_identical_snippets_in_one_file_stay_distinct_in_any_order():
    findings = _semgrep([_semgrep_result(5, "b" * 64), _semgrep_result(40, "b" * 64)])
    shifted = _semgrep([_semgrep_result(60, "b" * 64), _semgrep_result(7, "b" * 64)])

    fingerprints = [f["canonical_fingerprint"] for f in findings]
    assert len(set(fingerprints)) == 2
    # Occurrence index follows source order, not report order.
    assert {f["instance"]["line_start"]: f["canonical_fingerprint"] for f in findings}[5] == (
        {f["instance"]["line_start"]: f["canonical_fingerprint"] for f in shifted}[7]
    )


def test_semgrep_edited_snippet_or_other_repo_or_path_is_a_new_identity():
    base = _semgrep([_semgrep_result(10, "a" * 64)])[0]["canonical_fingerprint"]
    edited = _semgrep([_semgrep_result(10, "c" * 64)])[0]["canonical_fingerprint"]
    moved_file = _semgrep([_semgrep_result(10, "a" * 64, path="/workspace/source/src/other.py")])[0][
        "canonical_fingerprint"
    ]
    other_repo = normalize_semgrep_output({"results": [_semgrep_result(10, "a" * 64)]}, "repo-2")[0][
        "canonical_fingerprint"
    ]

    assert len({base, edited, moved_file, other_repo}) == 4


def test_semgrep_without_snippet_digest_still_separates_instances():
    findings = _semgrep([_semgrep_result(10, None), _semgrep_result(20, None)])

    assert findings[0]["canonical_fingerprint"] != findings[1]["canonical_fingerprint"]
    assert all(f["metadata_json"]["snippet_unavailable"] is True for f in findings)


def _checkov_check(lines: list[int], digest: str | None, resource: str = "aws_s3_bucket.b") -> dict:
    check = {
        "check_id": "CKV_AWS_20",
        "check_name": "Ensure the S3 bucket does not have public READ permissions",
        "file_path": "/main.tf",
        "file_line_range": lines,
        "resource": resource,
        "severity": "HIGH",
    }
    if digest is not None:
        check["snippet_sha256"] = digest
    return check


def _checkov(checks: list[dict]) -> list[dict]:
    return normalize_checkov_output({"results": {"failed_checks": checks}}, "repo-1")


def test_checkov_moved_block_keeps_fingerprint_and_edits_do_not():
    before = _checkov([_checkov_check([1, 4], "d" * 64)])[0]
    moved = _checkov([_checkov_check([31, 34], "d" * 64)])[0]
    edited = _checkov([_checkov_check([1, 4], "e" * 64)])[0]

    assert before["canonical_fingerprint"] == moved["canonical_fingerprint"]
    assert before["fingerprint_version"] == "fp.v3"
    assert before["canonical_fingerprint"] != edited["canonical_fingerprint"]
    assert moved["instance"]["line_start"] == 31


def test_checkov_identical_blocks_stay_distinct():
    findings = _checkov([_checkov_check([1, 4], "d" * 64), _checkov_check([10, 13], "d" * 64)])

    assert findings[0]["canonical_fingerprint"] != findings[1]["canonical_fingerprint"]


CANARY = "ghp_" + "Zx9Qw8Er7Ty6Ui5Op4As3Df2Gh1Jk0LmNbVc"


def _leak(line: int, rule: str = "github-pat", file: str = "/workspace/source/src/secret.py") -> dict:
    return {
        "RuleID": rule,
        "File": file,
        "StartLine": line,
        "EndLine": line,
        "Commit": "",
        "Match": CANARY,
        "Secret": CANARY,
    }


def test_gitleaks_moved_secret_keeps_fingerprint_and_second_match_is_distinct():
    before = normalize_gitleaks_output([_leak(3)], "repo-1")[0]
    moved = normalize_gitleaks_output([_leak(30)], "repo-1")[0]
    pair = normalize_gitleaks_output([_leak(3), _leak(9)], "repo-1")

    assert before["canonical_fingerprint"] == moved["canonical_fingerprint"]
    assert before["fingerprint_version"] == "fp.v3"
    assert pair[0]["canonical_fingerprint"] == before["canonical_fingerprint"]
    assert pair[1]["canonical_fingerprint"] != pair[0]["canonical_fingerprint"]
    other_rule = normalize_gitleaks_output([_leak(3, rule="aws-access-token")], "repo-1")[0]
    assert other_rule["canonical_fingerprint"] != before["canonical_fingerprint"]


def test_gitleaks_identity_is_independent_of_secret_value_canary():
    other_secret = dict(_leak(3), Match="ghp_" + "Qq" * 18, Secret="ghp_" + "Qq" * 18)

    first = normalize_gitleaks_output([_leak(3)], "repo-1")[0]
    second = normalize_gitleaks_output([other_secret], "repo-1")[0]

    assert first["canonical_fingerprint"] == second["canonical_fingerprint"]
    assert CANARY not in json.dumps(first)
