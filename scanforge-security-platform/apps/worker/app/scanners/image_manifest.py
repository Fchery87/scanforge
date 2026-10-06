from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ASSET_PATHS = {
    "trivy-db": "/opt/scanner-db/trivy/db",
    "trivy-java-db": "/opt/scanner-db/trivy/java-db",
    "trivy-checks": "/opt/scanner-db/trivy/policy",
    "grype-db": "/opt/scanner-db/grype",
    "osv-db": "/opt/scanner-db/osv/osv-scanner",
    "semgrep-rules": "/opt/scanner-rules/semgrep",
}
SCANNER_ASSETS = {
    "trivy": ("trivy-db", "trivy-java-db", "trivy-checks"),
    "grype": ("grype-db",),
    "osv": ("osv-db",),
    "semgrep": ("semgrep-rules",),
    "gitleaks": (),
    "syft": (),
    "checkov": (),
}
SUPPORTED_SCANNER_VERSIONS = {
    "trivy": "0.69.3",
    "gitleaks": "8.30.0",
    "semgrep": "1.156.0",
    "checkov": "3.2.513",
    "syft": "1.42.3",
    "grype": "0.110.0",
    "osv": "2.3.3",
}


def prepare_semgrep_rules(root: Path) -> list[Path]:
    import yaml

    retained = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Semgrep rules cannot contain symlinks")
        if not path.is_file():
            continue
        if path.suffix not in {".yaml", ".yml"} or path.name == "template.yaml" or any(
            marker in path.name for marker in (".test.", ".fixed.", ".fix.")
        ):
            path.unlink()
            continue
        try:
            document = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            path.unlink()
            continue
        rules = document.get("rules") if isinstance(document, dict) else None
        if not isinstance(rules, list) or not rules:
            path.unlink()
            continue
        retained.append(path)
    if not retained:
        raise ValueError("Semgrep rules bundle is empty")
    return retained


def build_manifest(versions: dict[str, str]) -> dict:
    if set(versions) != set(SCANNER_ASSETS):
        raise ValueError("manifest must include all scanner versions")
    for name, version in versions.items():
        binary = "osv-scanner" if name == "osv" else name
        output = subprocess.run(  # noqa: S603
            [binary, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        if not re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", output.stdout):
            raise ValueError("installed scanner version does not match the image manifest")
    assets = {}
    for name, directory in ASSET_PATHS.items():
        root = Path(directory)
        digest = hashlib.sha256()
        paths = sorted(path for path in root.rglob("*") if path.is_file())
        if not paths or any(path.is_symlink() for path in paths):
            raise ValueError("offline scanner assets are missing or unsafe")
        for path in paths:
            digest.update(str(path.relative_to(root)).encode())
            digest.update(b"\0")
            with path.open("rb") as content:
                for chunk in iter(lambda: content.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
        assets[name] = {"sha256": digest.hexdigest(), "path": directory}
    return {
        "schema_version": 1,
        "built_at": datetime.now(UTC).isoformat(),
        "scanners": versions,
        "assets": assets,
    }


def validate_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported scanner manifest")
    versions = manifest.get("scanners")
    assets = manifest.get("assets")
    if not isinstance(versions, dict) or set(versions) != set(SCANNER_ASSETS):
        raise ValueError("incomplete scanner manifest")
    if any(
        not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version) for version in versions.values()
    ):
        raise ValueError("invalid scanner version")
    if versions != SUPPORTED_SCANNER_VERSIONS:
        raise ValueError("unsupported scanner versions")
    if not isinstance(assets, dict) or set(assets) != set(ASSET_PATHS):
        raise ValueError("incomplete offline assets")
    for name, directory in ASSET_PATHS.items():
        asset = assets[name]
        if not isinstance(asset, dict) or asset.get("path") != directory:
            raise ValueError("invalid offline asset path")
        if not isinstance(asset.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
            raise ValueError("invalid offline asset digest")
    return manifest


def scanner_provenance(
    manifest: dict, scanner: str, image: str, arguments: tuple[str, ...] = (),
) -> dict[str, str]:
    assets = SCANNER_ASSETS[scanner]
    asset_digests = ":".join(manifest["assets"][name]["sha256"] for name in assets)
    configuration = json.dumps({"image": image, "arguments": arguments}, sort_keys=True, separators=(",", ":"))
    provenance = {"configuration_digest": hashlib.sha256(configuration.encode()).hexdigest()}
    if scanner in {"trivy", "grype", "osv"}:
        provenance["database_version"] = hashlib.sha256(asset_digests.encode()).hexdigest()
    if scanner == "semgrep":
        provenance["rules_version"] = manifest["assets"]["semgrep-rules"]["sha256"]
    elif scanner == "trivy":
        provenance["rules_version"] = manifest["assets"]["trivy-checks"]["sha256"]
    elif scanner in {"gitleaks", "checkov"}:
        provenance["rules_version"] = manifest["scanners"][scanner]
    return provenance


def main() -> None:
    if sys.argv[1] == "prepare-semgrep-rules":
        prepare_semgrep_rules(Path(ASSET_PATHS["semgrep-rules"]))
    elif sys.argv[1] == "build":
        versions = dict(value.split("=", 1) for value in sys.argv[2:])
        Path("/opt/scanner-manifest.json").write_text(json.dumps(build_manifest(versions)))
    elif sys.argv[1] == "verify":
        manifest = validate_manifest(json.loads(Path("/opt/scanner-manifest.json").read_text()))
        for directory in ASSET_PATHS.values():
            root = Path(directory)
            if not root.is_dir() or not any(path.is_file() and path.stat().st_size for path in root.rglob("*")):
                raise ValueError("offline scanner assets are unavailable")
        print(json.dumps(manifest))
    elif sys.argv[1] == "download-osv":
        from urllib.parse import quote
        from urllib.request import urlopen

        ecosystems = (
            "Go",
            "PyPI",
            "npm",
            "Maven",
            "NuGet",
            "Packagist",
            "RubyGems",
            "crates.io",
            "Hex",
            "Pub",
            "SwiftURL",
            "Hackage",
            "GHC",
            "GitHub Actions",
            "opam",
            "Julia",
            "CRAN",
        )
        for ecosystem in ecosystems:
            target = Path(ASSET_PATHS["osv-db"]) / ecosystem / "all.zip"
            target.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://osv-vulnerabilities.storage.googleapis.com/{quote(ecosystem, safe='')}/all.zip"
            with urlopen(url, timeout=120) as response, target.open("wb") as output:  # noqa: S310
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
    else:
        raise ValueError("unsupported manifest command")


if __name__ == "__main__":
    main()
