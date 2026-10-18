import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest


def test_scanner_image_is_digest_and_version_pinned():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile.scanners"
    content = dockerfile.read_text()

    assert "FROM python:3.12.8-slim-bookworm@sha256:" in content
    assert "REPLACE_WITH_VERIFIED_DIGEST" not in content
    for version in (
        "TRIVY_VERSION",
        "GITLEAKS_VERSION",
        "SEMGREP_VERSION",
        "CHECKOV_VERSION",
        "SYFT_VERSION",
        "GRYPE_VERSION",
        "OSV_SCANNER_VERSION",
    ):
        assert f"ARG {version}=" in content
    assert "/opt/scanner-manifest.json" in content
    assert "--download-db-only" in content
    assert "USER 65532:65532" in content


def test_scanner_image_build_versions_match_the_manifest_fixture():
    worker_dir = Path(__file__).resolve().parents[1]
    dockerfile = (worker_dir / "Dockerfile.scanners").read_text()
    manifest = json.loads((worker_dir / "tests/fixtures/scanners/manifest.json").read_text())
    build_arguments = {
        "TRIVY_VERSION": "trivy",
        "GITLEAKS_VERSION": "gitleaks",
        "SEMGREP_VERSION": "semgrep",
        "CHECKOV_VERSION": "checkov",
        "SYFT_VERSION": "syft",
        "GRYPE_VERSION": "grype",
        "OSV_SCANNER_VERSION": "osv-scanner",
    }

    for argument, scanner in build_arguments.items():
        match = re.search(rf"^ARG {argument}=([^\s]+)$", dockerfile, re.MULTILINE)
        assert match, f"{argument} is not pinned in Dockerfile.scanners"
        assert match.group(1) == manifest[scanner], f"{scanner} image and manifest versions differ"


def test_scanner_image_downloads_osv_offline_databases():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile.scanners").read_text()

    assert "GRYPE_DB_CACHE_DIR=/opt/scanner-db/grype grype db update" in dockerfile
    assert "GRYPE_DB_ROOT_DIR" not in dockerfile
    assert "https://osv-vulnerabilities.storage.googleapis.com/ecosystems.txt" in dockerfile
    assert 'encoded_ecosystem="$(printf \'%s\' "$ecosystem" | jq -sRr @uri)"' in dockerfile
    assert "https://osv-vulnerabilities.storage.googleapis.com/${encoded_ecosystem}/all.zip" in dockerfile
    assert '-o "/opt/scanner-db/osv/osv-scanner/$ecosystem/all.zip" || exit 1' in dockerfile


def test_scanner_image_verifies_executables_and_records_database_content_digests():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile.scanners").read_text()

    for command in (
        "trivy --version",
        "gitleaks version",
        "semgrep --version",
        "checkov --version",
        "syft version",
        "grype version",
        "osv-scanner --version",
    ):
        assert command in dockerfile
    for scanner in ("TRIVY", "GRYPE", "OSV"):
        assert f'{scanner}_DB_DIGEST="sha256:$(find ' in dockerfile
    assert "sha256:trivy-db-" not in dockerfile
    assert "sha256:grype-db-" not in dockerfile
    assert '"image_digest": "' not in dockerfile


def test_scanner_image_build_context_excludes_worker_code_and_local_environments():
    ignore_file = (Path(__file__).resolve().parents[1] / ".dockerignore").read_text().splitlines()

    assert ignore_file == ["**", "!app/", "!app/scanners/", "!app/scanners/rules/", "!app/scanners/rules/**"]


def test_worker_provisions_provenance_from_the_configured_image(tmp_path, monkeypatch):
    from app.runtime.base import provision_scanner_manifest
    from app.runtime.docker import DockerScanRuntime
    from app.scanners.registry import SCANNER_REGISTRY

    worker_dir = Path(__file__).resolve().parents[1]
    manifest = json.loads((worker_dir / "tests/fixtures/scanners/manifest.json").read_text())
    image_digest = "sha256:" + "a" * 64
    destination = tmp_path / "scanner-manifest.json"
    monkeypatch.delenv("SCANNER_MANIFEST_PATH", raising=False)
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime(image_digest)
    monkeypatch.setattr(runtime, "read_image_file", lambda _path: json.dumps(manifest))

    result_path = provision_scanner_manifest(runtime, destination)
    provisioned = json.loads(result_path.read_text())
    assert result_path == destination
    assert result_path.stat().st_mode & 0o777 == 0o600
    assert provisioned["image_digest"] == image_digest
    assert set(provisioned["scanners"]) == set(SCANNER_REGISTRY)
    assert os.environ["SCANNER_MANIFEST_PATH"] == str(destination)

    provenance = SCANNER_REGISTRY["trivy"].adapter_factory().resolve_provenance()
    assert provenance["version"] == manifest["scanners"]["trivy"]["scanner_version"]
    assert provenance["db_digest"] == manifest["scanners"]["trivy"]["db_digest"]
    assert provenance["image_digest"] == image_digest


def test_worker_rejects_incomplete_database_provenance(tmp_path, monkeypatch):
    from app.runtime.base import provision_scanner_manifest
    from app.runtime.docker import DockerScanRuntime

    worker_dir = Path(__file__).resolve().parents[1]
    manifest = json.loads((worker_dir / "tests/fixtures/scanners/manifest.json").read_text())
    del manifest["scanners"]["trivy"]["db_digest"]
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        runtime = DockerScanRuntime("sha256:" + "b" * 64)
    monkeypatch.setattr(runtime, "read_image_file", lambda _path: json.dumps(manifest))

    with pytest.raises(RuntimeError, match="trivy database identity"):
        provision_scanner_manifest(runtime, tmp_path / "scanner-manifest.json")
