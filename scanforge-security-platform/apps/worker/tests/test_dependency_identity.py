"""P1.5 (#39): dependency finding identity is ecosystem- and scanner-aware (ADR-014)."""
import hashlib

import pytest

from app.normalizers import dependency_identity
from app.normalizers.grype import normalize_grype_output
from app.normalizers.osv import normalize_osv_output
from app.normalizers.trivy import normalize_trivy_output

REPO = "repo-1"
ADVISORY = "CVE-2024-0001"


def _osv(ecosystem: str, name: str = "left-pad", version: str = "1.0.0", source: str | None = None):
    result = {
        "packages": [
            {
                "package": {"name": name, "ecosystem": ecosystem, "version": version},
                "vulnerabilities": [{"id": ADVISORY, "summary": "x"}],
            }
        ]
    }
    if source:
        result["source"] = {"path": source}
    return {"results": [result]}


def _trivy(*targets: str, name: str = "left-pad", version: str = "1.0.0", rtype: str = "npm"):
    return {
        "Results": [
            {
                "Target": target,
                "Type": rtype,
                "Vulnerabilities": [
                    {
                        "PkgName": name,
                        "InstalledVersion": version,
                        "VulnerabilityID": ADVISORY,
                        "Severity": "HIGH",
                    }
                ],
            }
            for target in targets
        ]
    }


def _grype(name: str = "left-pad", version: str = "1.0.0", ptype: str = "npm"):
    return {
        "matches": [
            {
                "artifact": {"name": name, "version": version, "type": ptype},
                "vulnerability": {"id": ADVISORY, "severity": "High"},
            }
        ]
    }


def _fp(scanner: str, ecosystem: str | None = "npm") -> str:
    return dependency_identity.compute_dependency_fingerprint(
        repository_id=REPO,
        ecosystem=ecosystem,
        package_name="left-pad",
        installed_version="1.0.0",
        advisory_id=ADVISORY,
        scanner=scanner,
    )


def test_same_package_name_in_different_ecosystems_never_shares_a_finding():
    npm = normalize_osv_output(_osv("npm", name="requests"), REPO)[0]
    pypi = normalize_osv_output(_osv("PyPI", name="requests"), REPO)[0]
    assert npm["canonical_fingerprint"] != pypi["canonical_fingerprint"]

    trivy_npm = normalize_trivy_output(_trivy("package-lock.json", rtype="npm"), REPO)[0]
    trivy_pip = normalize_trivy_output(_trivy("requirements.txt", rtype="pip"), REPO)[0]
    assert trivy_npm["canonical_fingerprint"] != trivy_pip["canonical_fingerprint"]

    grype_npm = normalize_grype_output(_grype(ptype="npm"), REPO)[0]
    grype_py = normalize_grype_output(_grype(ptype="python"), REPO)[0]
    assert grype_npm["canonical_fingerprint"] != grype_py["canonical_fingerprint"]


def test_two_scanners_reporting_the_same_advisory_stay_separate():
    fingerprints = {
        normalize_trivy_output(_trivy("package-lock.json"), REPO)[0]["canonical_fingerprint"],
        normalize_osv_output(_osv("npm"), REPO)[0]["canonical_fingerprint"],
        normalize_grype_output(_grype(), REPO)[0]["canonical_fingerprint"],
    }
    assert len(fingerprints) == 3


def test_dependency_findings_declare_the_fp_v3_policy():
    findings = (
        normalize_trivy_output(_trivy("package-lock.json"), REPO)
        + normalize_osv_output(_osv("npm"), REPO)
        + normalize_grype_output(_grype(), REPO)
    )
    assert {f["fingerprint_version"] for f in findings} == {"fp.v3"}


def test_fp_v3_identity_is_not_the_legacy_fp_v2_hash():
    legacy = hashlib.sha256(f"left-pad|1.0.0|{ADVISORY}|{REPO}".encode()).hexdigest()
    current = normalize_osv_output(_osv("npm"), REPO)[0]["canonical_fingerprint"]
    assert current != legacy


def test_identity_is_stable_across_runs_and_sensitive_to_every_component():
    base = normalize_osv_output(_osv("npm"), REPO)[0]["canonical_fingerprint"]
    assert normalize_osv_output(_osv("npm"), REPO)[0]["canonical_fingerprint"] == base
    assert normalize_osv_output(_osv("npm", version="1.0.1"), REPO)[0]["canonical_fingerprint"] != base
    assert normalize_osv_output(_osv("npm", name="right-pad"), REPO)[0]["canonical_fingerprint"] != base
    assert normalize_osv_output(_osv("npm"), "repo-2")[0]["canonical_fingerprint"] != base


def test_same_advisory_in_two_manifests_is_one_finding_with_two_instances():
    findings = normalize_trivy_output(_trivy("a/package-lock.json", "b/package-lock.json"), REPO)

    assert len(findings) == 2
    assert findings[0]["canonical_fingerprint"] == findings[1]["canonical_fingerprint"]
    assert {f["instance"]["path"] for f in findings} == {"a/package-lock.json", "b/package-lock.json"}

    osv = normalize_osv_output(
        {
            "results": _osv("npm", source="a/package-lock.json")["results"]
            + _osv("npm", source="b/package-lock.json")["results"]
        },
        REPO,
    )
    assert len(osv) == 2
    assert osv[0]["canonical_fingerprint"] == osv[1]["canonical_fingerprint"]
    assert {f["instance"]["path"] for f in osv} == {"a/package-lock.json", "b/package-lock.json"}


def test_cross_scanner_equivalence_table_is_initially_empty():
    assert dependency_identity.SCANNER_EQUIVALENCE == {}


def test_an_equivalence_entry_is_the_only_way_scanners_merge(monkeypatch):
    assert _fp("osv") != _fp("grype")
    monkeypatch.setitem(dependency_identity.SCANNER_EQUIVALENCE, "osv", "shared")
    monkeypatch.setitem(dependency_identity.SCANNER_EQUIVALENCE, "grype", "shared")
    assert _fp("osv") == _fp("grype")
    assert _fp("osv") != _fp("trivy")


@pytest.mark.parametrize("ecosystem", [None, ""])
def test_missing_ecosystem_is_explicit_unknown_not_a_wildcard(ecosystem):
    assert _fp("osv", ecosystem) != _fp("osv", "npm")


def test_component_boundaries_cannot_be_forged():
    a = dependency_identity.compute_dependency_fingerprint(
        repository_id=REPO,
        ecosystem="npm",
        package_name="a|b",
        installed_version="c",
        advisory_id=ADVISORY,
        scanner="osv",
    )
    b = dependency_identity.compute_dependency_fingerprint(
        repository_id=REPO,
        ecosystem="npm",
        package_name="a",
        installed_version="b|c",
        advisory_id=ADVISORY,
        scanner="osv",
    )
    assert a != b
