from types import SimpleNamespace

from app.services.remediation_guidance import build_remediation_guidance


def test_remediation_guidance_uses_dependency_evidence_and_references():
    finding = SimpleNamespace(
        category="vulnerability",
        severity="high",
        title="Vulnerable dependency",
        fixed_version="2.0.0",
        references=[SimpleNamespace(url="https://advisory.example/CVE-1")],
        instances=[SimpleNamespace(package_name="django", installed_version="1.0.0", path="requirements.txt")],
    )

    guidance = build_remediation_guidance(finding)

    assert guidance == {
        "summary": "Update django from 1.0.0 to 2.0.0.",
        "steps": [
            "Review the affected dependency in requirements.txt.",
            "Upgrade django to 2.0.0.",
            "Run the relevant dependency and regression tests.",
        ],
        "references": ["https://advisory.example/CVE-1"],
    }


def test_remediation_guidance_falls_back_to_structured_review():
    finding = SimpleNamespace(
        category="code_quality",
        severity="medium",
        title="Unsafe pattern",
        fixed_version=None,
        references=[],
        instances=[SimpleNamespace(package_name=None, installed_version=None, path="src/app.py")],
    )

    guidance = build_remediation_guidance(finding)

    assert guidance["summary"] == "Review and remediate Unsafe pattern."
    assert guidance["steps"][0] == "Inspect the affected evidence in src/app.py."
