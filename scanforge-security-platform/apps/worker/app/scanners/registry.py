from collections.abc import Callable
from dataclasses import dataclass

from app.scanners.base import ScannerAdapter

Normalizer = Callable[[dict, str], list[dict]]


@dataclass(frozen=True)
class ScannerRegistration:
    name: str
    adapter_factory: Callable[[], ScannerAdapter]
    normalize: Normalizer


SCAN_MODE_REGISTRY: dict[str, list[str]] = {
    # ADR-019: Trivy is the primary dependency engine; OSV and Grype stay registered but are opt-in.
    "scan.repo.full": ["trivy", "gitleaks", "semgrep", "syft", "checkov"],
    "scan.repo.diff": ["gitleaks", "semgrep", "checkov"],
    "scan.dependencies": ["trivy", "osv", "syft", "grype"],
    "scan.secrets": ["gitleaks"],
}


# Capability -> scanners, for absence eligibility (P1.6). Mirrored by CAPABILITY_SCANNERS in the API
# evidence contract (which additionally accepts the alias "osv-scanner" for "osv"); the API owns the
# decision, this map only keeps the two sides legible together.
CAPABILITY_REGISTRY: dict[str, list[str]] = {
    "secrets": ["gitleaks"],
    "sast": ["semgrep"],
    "dependencies": ["trivy", "osv", "syft", "grype"],
    "iac": ["checkov"],
}


def _build_registry() -> dict[str, ScannerRegistration]:
    from app.normalizers.checkov import normalize_checkov_output
    from app.normalizers.gitleaks import normalize_gitleaks_output
    from app.normalizers.grype import normalize_grype_output
    from app.normalizers.osv import normalize_osv_output
    from app.normalizers.semgrep import normalize_semgrep_output
    from app.normalizers.syft import normalize_syft_output
    from app.normalizers.trivy import normalize_trivy_output
    from app.scanners.checkov import CheckovAdapter
    from app.scanners.gitleaks import GitleaksAdapter
    from app.scanners.grype import GrypeAdapter
    from app.scanners.osv import OsvAdapter
    from app.scanners.semgrep import SemgrepAdapter
    from app.scanners.syft import SyftAdapter
    from app.scanners.trivy import TrivyAdapter

    return {
        "trivy": ScannerRegistration("trivy", TrivyAdapter, normalize_trivy_output),
        "gitleaks": ScannerRegistration("gitleaks", GitleaksAdapter, normalize_gitleaks_output),
        "osv": ScannerRegistration("osv", OsvAdapter, normalize_osv_output),
        "semgrep": ScannerRegistration("semgrep", SemgrepAdapter, normalize_semgrep_output),
        "syft": ScannerRegistration("syft", SyftAdapter, normalize_syft_output),
        "checkov": ScannerRegistration("checkov", CheckovAdapter, normalize_checkov_output),
        "grype": ScannerRegistration("grype", GrypeAdapter, normalize_grype_output),
    }


SCANNER_REGISTRY = _build_registry()


def scanners_for_scan_type(scan_type: str) -> list[str]:
    return SCAN_MODE_REGISTRY.get(scan_type, SCAN_MODE_REGISTRY["scan.repo.full"])
