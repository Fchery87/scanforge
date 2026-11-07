from app.scanners.registry import SCAN_MODE_REGISTRY, SCANNER_REGISTRY, scanners_for_scan_type


def test_every_scan_mode_scanner_has_adapter_and_normalizer_registration():
    registered = set(SCANNER_REGISTRY)

    for scanner_names in SCAN_MODE_REGISTRY.values():
        assert set(scanner_names) <= registered

    for registration in SCANNER_REGISTRY.values():
        assert registration.adapter_factory is not None
        assert registration.normalize is not None


def test_scanners_for_unknown_scan_type_defaults_to_full_scan():
    assert scanners_for_scan_type("unknown") == SCAN_MODE_REGISTRY["scan.repo.full"]


def test_default_full_scan_runs_primary_dependency_engine_and_inventory_only():
    """ADR-019: Trivy is the primary dependency engine, Syft supplies inventory.

    OSV-Scanner and Grype stay registered but are not part of the default full scan.
    """
    expected = ["trivy", "gitleaks", "semgrep", "syft", "checkov"]
    assert SCAN_MODE_REGISTRY["scan.repo.full"] == expected
    assert scanners_for_scan_type("scan.repo.full") == expected


def test_secondary_dependency_engines_stay_registered_but_not_default_for_full_scans():
    assert {"osv", "grype"} <= set(SCANNER_REGISTRY)
    assert "osv" not in SCAN_MODE_REGISTRY["scan.repo.full"]
    assert "grype" not in SCAN_MODE_REGISTRY["scan.repo.full"]
