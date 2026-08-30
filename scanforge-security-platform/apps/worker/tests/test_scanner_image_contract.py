from pathlib import Path


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
