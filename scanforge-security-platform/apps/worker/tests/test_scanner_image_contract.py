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


def test_semgrep_bundle_keeps_only_rules_and_removes_repository_configuration(tmp_path):
    from app.scanners.image_manifest import prepare_semgrep_rules

    documents = {
        "python/rule.yaml": (
            "rules:\n  - id: actual-rule\n    pattern: $X == $X\n    message: Equality\n"
            "    languages: [python]\n    severity: WARNING\n"
        ),
        ".pre-commit-config.yaml": "repos:\n  - repo: https://example.test/hooks\n",
        ".github/workflows/build.yml": "jobs:\n  build: {}\n",
        "python/rule.test.yaml": "rules:\n  - id: fixture\n",
        "template.yaml": "rules:\n  - id: eqeq-is-bad\n",
        "metadata.yaml": "name: example\n",
        "malformed.yaml": "rules: [\n",
        "README.md": "Repository documentation",
    }
    for name, content in documents.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    retained = prepare_semgrep_rules(tmp_path)
    assert [str(path.relative_to(tmp_path)) for path in retained] == ["python/rule.yaml"]
    assert [str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_file()] == ["python/rule.yaml"]


def test_semgrep_bundle_fails_when_no_rules_remain(tmp_path):
    import pytest

    from app.scanners.image_manifest import prepare_semgrep_rules

    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    with pytest.raises(ValueError, match="empty"):
        prepare_semgrep_rules(tmp_path)


def test_configuration_provenance_changes_with_contained_arguments():
    from app.scanners.image_manifest import scanner_provenance
    manifest = {"assets": {}, "scanners": {"syft": "1.42.3"}}
    first = scanner_provenance(manifest, "syft", "scanner@sha256:" + "a" * 64, ("scan", "--offline"))
    assert first == scanner_provenance(manifest, "syft", "scanner@sha256:" + "a" * 64, ("scan", "--offline"))
    assert first != scanner_provenance(manifest, "syft", "scanner@sha256:" + "a" * 64, ("scan", "--other"))
