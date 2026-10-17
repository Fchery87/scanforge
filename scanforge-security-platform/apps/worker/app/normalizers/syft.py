import hashlib
import re

RESTRICTIVE_LICENSES = {
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "SSPL-1.0",
}

RESTRICTIVE_LICENSE_PREFIXES = (
    "LGPL-",
    "CC-BY-SA-",
    "CC-BY-NC-",
)


def _normalize_repo_path(path: str) -> str:
    cleaned = str(path or "").strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned


def _is_restrictive_license(license_id: str) -> bool:
    if license_id in RESTRICTIVE_LICENSES:
        return True
    for prefix in RESTRICTIVE_LICENSE_PREFIXES:
        if license_id.startswith(prefix):
            return True
    return False


def compute_license_fingerprint(
    package_name: str,
    license_id: str,
    repo_id: str,
) -> str:
    components = [
        package_name.lower(),
        license_id,
        repo_id,
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_syft_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []

    artifacts = raw_output.get("artifacts", []) if isinstance(raw_output, dict) else []
    if isinstance(raw_output, list):
        artifacts = raw_output

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        name = artifact.get("name", "")
        version = artifact.get("version", "")
        pkg_type = artifact.get("type", "")
        purl = artifact.get("purl", "")
        licenses = artifact.get("licenses", []) or []
        locations = artifact.get("locations", []) or []
        path = _normalize_repo_path(locations[0].get("path", "")) if locations else ""

        if not name:
            continue

        license_values = []
        for lic in licenses:
            spdx = lic.get("spdxExpression", "") or lic.get("value", "")
            if spdx:
                license_values.append(spdx)

        for license_id in license_values:
            if _is_restrictive_license(license_id):
                fingerprint = compute_license_fingerprint(
                    package_name=name,
                    license_id=license_id,
                    repo_id=repository_id,
                )

                finding = {
                    "category": "license_compliance",
                    "severity": "medium",
                    "title": f"Restrictive license: {name}@{version} ({license_id})",
                    "description": (
                        f"Package {name}@{version} uses restrictive license {license_id}"
                        " which may impose obligations on derivative works."
                    ),
                    "canonical_fingerprint": fingerprint,
                    "primary_scanner": "syft",
                    "confidence_score": 0.9,
                    "package_name": name,
                    "package_ecosystem": pkg_type or None,
                    "metadata_json": {
                        "severity_source": "syft",
                        "raw_severity": "MEDIUM",
                        "license_id": license_id,
                    },
                    "instance": {
                        "package_name": name,
                        "installed_version": version,
                        "package_type": pkg_type,
                        "license": license_id,
                        "purl": purl,
                        "path": path,
                    },
                    "references": [
                        {
                            "type": "documentation",
                            "value": license_id,
                            "url": f"https://spdx.org/licenses/{license_id}.html",
                        }
                    ],
                }
                findings.append(finding)

        if not license_values:
            fingerprint = compute_license_fingerprint(
                package_name=name,
                license_id="NO_LICENSE",
                repo_id=repository_id,
            )

            finding = {
                "category": "license_compliance",
                "severity": "low",
                "title": f"No license declared: {name}@{version}",
                "description": (
                    f"Package {name}@{version} has no license declared."
                    " This may pose legal risks for usage and distribution."
                ),
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "syft",
                "confidence_score": 0.7,
                "package_name": name,
                "package_ecosystem": pkg_type or None,
                "metadata_json": {
                    "severity_source": "syft",
                    "raw_severity": "LOW",
                    "license_id": "NO_LICENSE",
                },
                "instance": {
                    "package_name": name,
                    "installed_version": version,
                    "package_type": pkg_type,
                    "license": None,
                    "purl": purl,
                    "path": path,
                },
                "references": [
                    {
                        "type": "documentation",
                        "value": "NOASSERTION",
                        "url": "https://spdx.org/licenses/",
                    }
                ],
            }
            findings.append(finding)

    return findings
