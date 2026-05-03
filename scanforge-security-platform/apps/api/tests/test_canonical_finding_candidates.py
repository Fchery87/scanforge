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
