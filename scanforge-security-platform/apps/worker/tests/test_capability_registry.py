from app.scanners.registry import CAPABILITY_REGISTRY, SCAN_MODE_REGISTRY, SCANNER_REGISTRY


def test_capability_map_pins_the_scanner_to_capability_assignment():
    assert CAPABILITY_REGISTRY == {
        "secrets": ["gitleaks"],
        "sast": ["semgrep"],
        "dependencies": ["trivy", "osv", "syft", "grype"],
        "iac": ["checkov"],
    }


def test_every_scanner_belongs_to_exactly_one_capability():
    assigned = [name for names in CAPABILITY_REGISTRY.values() for name in names]
    assert sorted(assigned) == sorted(SCANNER_REGISTRY)


def test_every_default_full_scan_capability_has_a_scanner():
    full = set(SCAN_MODE_REGISTRY["scan.repo.full"])
    for names in CAPABILITY_REGISTRY.values():
        assert full & set(names)
