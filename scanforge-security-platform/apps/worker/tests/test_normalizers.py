from app.normalizers.checkov import normalize_checkov_output
from app.normalizers.gitleaks import normalize_gitleaks_output
from app.normalizers.grype import normalize_grype_output
from app.normalizers.osv import _get_severity, normalize_osv_output
from app.normalizers.semgrep import normalize_semgrep_output
from app.normalizers.trivy import normalize_trivy_output


def test_trivy_normalizes_misconfigurations():
    raw_output = {
        "Results": [
            {
                "Target": "infra/main.tf",
                "Type": "terraform",
                "Misconfigurations": [
                    {
                        "ID": "AVD-AWS-0001",
                        "Title": "S3 bucket is public",
                        "Description": "Bucket is exposed to the internet",
                        "Severity": "HIGH",
                        "Resolution": "Disable public access",
                    }
                ],
            }
        ]
    }

    findings = normalize_trivy_output(raw_output, "repo-1")

    assert len(findings) == 1
    assert findings[0]["category"] == "iac_misconfiguration"
    assert findings[0]["severity"] == "high"
    assert findings[0]["instance"]["path"] == "infra/main.tf"


def test_semgrep_fingerprint_includes_line_number():
    raw_output = {
        "results": [
            {
                "check_id": "python.lang.security.audit.subprocess-shell-true",
                "path": "src/app.py",
                "start": {"line": 10},
                "end": {"line": 10},
                "extra": {
                    "severity": "ERROR",
                    "message": "Dangerous subprocess usage",
                    "metadata": {"category": "security", "confidence": "HIGH"},
                },
            },
            {
                "check_id": "python.lang.security.audit.subprocess-shell-true",
                "path": "src/app.py",
                "start": {"line": 20},
                "end": {"line": 20},
                "extra": {
                    "severity": "ERROR",
                    "message": "Dangerous subprocess usage",
                    "metadata": {"category": "security", "confidence": "HIGH"},
                },
            },
        ]
    }

    findings = normalize_semgrep_output(raw_output, "repo-1")

    assert len(findings) == 2
    assert findings[0]["canonical_fingerprint"] != findings[1]["canonical_fingerprint"]


def test_osv_cvss_v3_maps_to_critical():
    vuln = {
        "severity": [
            {
                "type": "CVSS_V3",
                "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            }
        ]
    }

    assert _get_severity(vuln) == "critical"


def test_osv_normalizes_simple_results_shape():
    raw_output = {
        "results": [
            {
                "packages": [
                    {
                        "package": {"name": "requests", "ecosystem": "PyPI"},
                        "version": "2.19.0",
                        "vulnerabilities": [
                            {
                                "id": "GHSA-xxxx-yyyy-zzzz",
                                "summary": "Example vuln",
                                "severity": [
                                    {
                                        "type": "CVSS_V3",
                                        "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ]
    }

    findings = normalize_osv_output(raw_output, "repo-1")

    assert len(findings) == 1
    assert findings[0]["instance"]["package_name"] == "requests"
    assert findings[0]["instance"]["installed_version"] == "2.19.0"
    assert findings[0]["severity"] == "critical"


def test_checkov_normalizes_failed_checks():
    raw_output = {
        "results": {
            "failed_checks": [
                {
                    "check_id": "CKV_AWS_20",
                    "check_name": "S3 bucket versioning should be enabled",
                    "check_result": {"result": "FAILED"},
                    "file_path": "/infra/main.tf",
                    "file_line_range": [12, 24],
                    "resource": "aws_s3_bucket.logs",
                    "severity": "HIGH",
                    "guideline": "https://docs.prismacloud.io/example",
                }
            ]
        }
    }

    findings = normalize_checkov_output(raw_output, "repo-1")

    assert len(findings) == 1
    assert findings[0]["category"] == "iac_misconfiguration"
    assert findings[0]["severity"] == "high"
    assert findings[0]["instance"]["path"] == "infra/main.tf"
    assert findings[0]["instance"]["resource"] == "aws_s3_bucket.logs"


def test_grype_normalizes_matches():
    raw_output = {
        "matches": [
            {
                "artifact": {
                    "name": "requests",
                    "version": "2.19.0",
                    "type": "python",
                    "locations": [{"path": "/workspace/requirements.txt"}],
                },
                "vulnerability": {
                    "id": "CVE-2023-12345",
                    "severity": "High",
                    "fix": {"versions": ["2.31.0"]},
                    "dataSource": "https://grype.example/advisory",
                },
            }
        ]
    }

    findings = normalize_grype_output(raw_output, "repo-1")

    assert len(findings) == 1
    assert findings[0]["category"] == "vulnerability"
    assert findings[0]["severity"] == "high"
    assert findings[0]["instance"]["package_name"] == "requests"
    assert findings[0]["instance"]["path"] == "/workspace/requirements.txt"
    assert findings[0]["fixed_version"] == "2.31.0"


def test_gitleaks_normalizes_top_level_list_output():
    raw_output = [
        {
            "RuleID": "github_token",
            "File": "src/config.py",
            "StartLine": 12,
            "EndLine": 12,
            "Match": "ghp_exampletoken",
        }
    ]

    findings = normalize_gitleaks_output(raw_output, "repo-1")

    assert len(findings) == 1
    assert findings[0]["category"] == "secret"
    assert findings[0]["severity"] == "critical"
    assert findings[0]["instance"]["path"] == "src/config.py"


def test_semgrep_keeps_severity_and_confidence_separate():
    raw_output = {
        "results": [
            {
                "check_id": "python.lang.security.audit.subprocess-shell-true",
                "path": "src/app.py",
                "start": {"line": 10},
                "end": {"line": 10},
                "extra": {
                    "severity": "ERROR",
                    "message": "Dangerous subprocess usage",
                    "metadata": {"category": "security", "confidence": "HIGH"},
                },
            }
        ]
    }

    findings = normalize_semgrep_output(raw_output, "repo-1")

    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["confidence_score"] == 0.95
    assert findings[0]["metadata_json"]["raw_severity"] == "ERROR"
    assert findings[0]["metadata_json"]["raw_confidence"] == "HIGH"
    assert findings[0]["metadata_json"]["severity_source"] == "semgrep"


def test_normalization_stage_preserves_conflicting_provider_values():
    from app.scanners.base import ScannerResult
    from app.services.scan_pipeline.context import ScanContext
    from app.services.scan_pipeline.normalization import NormalizationStage

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
        "trivy": ScannerResult(
            scanner_name="trivy",
            success=True,
            raw_output={
                "Results": [
                    {
                        "Target": "requirements.txt",
                        "Type": "pip",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-2023-12345",
                                "PkgName": "requests",
                                "InstalledVersion": "2.19.0",
                                "FixedVersion": "2.31.0",
                                "Severity": "MEDIUM",
                                "Description": "Trivy description",
                            }
                        ],
                    }
                ]
            },
        ),
        "grype": ScannerResult(
            scanner_name="grype",
            success=True,
            raw_output={
                "matches": [
                    {
                        "artifact": {
                            "name": "requests",
                            "version": "2.19.0",
                            "type": "python",
                            "locations": [{"path": "requirements.txt"}],
                        },
                        "vulnerability": {
                            "id": "CVE-2023-12345",
                            "severity": "High",
                            "fix": {"versions": ["2.32.0"]},
                            "dataSource": "https://grype.example/advisory",
                        },
                    }
                ]
            },
        ),
    }

    findings = NormalizationStage().normalize_results(context)
    assert len(findings) == 1
    reconciled = findings[0]
    assert reconciled["severity"] == "high"
    assert reconciled["fixed_version"] is None
    assert reconciled["metadata_json"]["severity_source"] == "grype"
    assert reconciled["metadata_json"]["severity_conflict"] is True
    assert reconciled["metadata_json"]["provider_severities"] == {"trivy": "medium", "grype": "high"}
    assert reconciled["metadata_json"]["remediation_conflict"] is True
    assert reconciled["metadata_json"]["provider_fixed_versions"] == {
        "trivy": "2.31.0",
        "grype": "2.32.0",
    }
    assert len(reconciled["metadata_json"]["provider_observations"]) == 2
