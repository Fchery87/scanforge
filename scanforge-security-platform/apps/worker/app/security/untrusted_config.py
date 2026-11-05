"""Scanner configuration shipped inside an untrusted (fork) repository.

Scanners auto-discover configuration from the scanned tree or working directory
(for example Checkov's ``.checkov.yaml`` can name an external checks directory).
A fork pull request must not choose how it is scanned, so these files are removed
from the acquired fork tree before any scanner runs. Scanner configuration comes
only from the trusted, digest-pinned rules bundled with the worker.
"""

from __future__ import annotations

import os
from pathlib import Path

UNTRUSTED_SCANNER_CONFIG_NAMES: frozenset[str] = frozenset(
    {
        ".checkov.yaml",
        ".checkov.yml",
        ".checkov.baseline",
        ".gitleaks.toml",
        ".gitleaksignore",
        ".trivyignore",
        ".trivy.yaml",
        "trivy.yaml",
        "trivy.yml",
        "osv-scanner.toml",
        ".semgrepignore",
        ".semgrep.yml",
        ".semgrep.yaml",
        ".grype.yaml",
        ".grype.yml",
        ".syft.yaml",
        ".syft.yml",
    }
)


def remove_untrusted_scanner_config(root: Path) -> list[str]:
    """Delete scanner configuration files under ``root``; return their relative paths.

    Symlinks are unlinked, never followed, so a link cannot make this touch files
    outside the acquired tree.
    """
    removed: list[str] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        if ".git" in dirs:
            dirs.remove(".git")
        for name in files:
            if name in UNTRUSTED_SCANNER_CONFIG_NAMES:
                path = current_path / name
                path.unlink()
                removed.append(path.relative_to(root).as_posix())
        # Directory symlinks are listed in dirs but never descended into; a link named
        # like a config file is removed without following it.
        for name in list(dirs):
            path = current_path / name
            if name in UNTRUSTED_SCANNER_CONFIG_NAMES and path.is_symlink():
                path.unlink()
                dirs.remove(name)
                removed.append(path.relative_to(root).as_posix())
    return removed
