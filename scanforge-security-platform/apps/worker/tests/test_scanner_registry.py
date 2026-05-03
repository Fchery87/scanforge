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
