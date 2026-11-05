"""Dependency finding identity under fingerprint policy fp.v3 (ADR-014).

Identity is repository + ecosystem + package + installed version + advisory +
scanner. Scanners are never merged by guesswork: results from different
scanners merge only through SCANNER_EQUIVALENCE, which is initially empty. An
entry may be added only with fixtures proving both scanners report the same
ecosystem vocabulary and advisory identifiers for the same package. Manifest
paths are not part of identity; they are retained as finding instances.
"""

import hashlib
import json

DEPENDENCY_FINGERPRINT_VERSION = "fp.v3"

# scanner name -> equivalence group name. Scanners absent from the table are
# their own group, so unknown equivalence stays separate.
SCANNER_EQUIVALENCE: dict[str, str] = {}


def compute_dependency_fingerprint(
    *,
    repository_id: str,
    ecosystem: str | None,
    package_name: str,
    installed_version: str,
    advisory_id: str,
    scanner: str,
) -> str:
    components = [
        DEPENDENCY_FINGERPRINT_VERSION,
        "dependency",
        repository_id,
        (ecosystem or "").strip().lower() or "unknown",
        package_name.strip().lower(),
        installed_version,
        advisory_id,
        SCANNER_EQUIVALENCE.get(scanner, scanner),
    ]
    # JSON encoding keeps component boundaries unforgeable by separator characters.
    return hashlib.sha256(json.dumps(components, separators=(",", ":")).encode()).hexdigest()
