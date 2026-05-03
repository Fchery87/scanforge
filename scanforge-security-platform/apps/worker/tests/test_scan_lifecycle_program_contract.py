from app.scanners.registry import SCAN_MODE_REGISTRY, SCANNER_REGISTRY


def test_scan_lifecycle_program_contract_has_registered_scanner_normalization_for_all_modes():
    for scanner_names in SCAN_MODE_REGISTRY.values():
        for scanner_name in scanner_names:
            registration = SCANNER_REGISTRY[scanner_name]
            assert registration.adapter_factory is not None
            assert registration.normalize is not None
