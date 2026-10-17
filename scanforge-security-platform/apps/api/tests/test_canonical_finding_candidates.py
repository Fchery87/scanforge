from app.schemas.canonical_findings import CanonicalFindingCandidate


def test_canonical_finding_candidate_preserves_evidence_without_mutating_source_dict():
    source = {
        "canonical_fingerprint": "fp-1",
        "severity": "high",
        "category": "vulnerability",
        "title": "Vulnerable dependency",
        "instance": {"path": "requirements.txt", "package_name": "django", "target": "requirements.txt"},
        "references": [{"type": "advisory", "value": "CVE-1", "url": "https://example.test/CVE-1"}],
    }

    candidate = CanonicalFindingCandidate.model_validate(source)

    assert candidate.canonical_fingerprint == "fp-1"
    assert candidate.instance.path == "requirements.txt"
    assert candidate.instance.model_extra == {"target": "requirements.txt"}
    assert candidate.references[0].value == "CVE-1"
    assert "instance" in source
    assert "references" in source


def test_canonical_finding_candidate_records_fingerprint_version_and_provenance():
    candidate = CanonicalFindingCandidate.model_validate(
        {
            "canonical_fingerprint": "fp.v2:dep:pypi:django:4.2.0:CVE-2026-0001",
            "fingerprint_version": "fp.v2",
            "severity": "high",
            "category": "vulnerability",
            "title": "Django SQLi",
            "primary_scanner": "trivy",
            "advisory_id": "CVE-2026-0001",
            "package_ecosystem": "pypi",
            "package_name": "django",
            "instance": {
                "path": "requirements.txt",
                "package_name": "django",
                "installed_version": "4.2.0",
                "fixed_version": "4.2.15",
            },
        }
    )

    assert candidate.fingerprint_version == "fp.v2"
    assert candidate.advisory_id == "CVE-2026-0001"
    assert candidate.package_ecosystem == "pypi"
    assert candidate.package_name == "django"

