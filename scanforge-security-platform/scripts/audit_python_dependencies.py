"""Audit installed dependencies, excluding only this project's editable install."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib


def requirements_for(packages, project_name, project_dir):
    """Keep all installed versions, including any third-party editable packages."""
    def normalize(name):
        return re.sub(r"[-_.]+", "-", name).lower()

    requirements = []
    excluded = 0
    for package in packages:
        location = package.get("editable_project_location")
        if (
            normalize(package["name"]) == normalize(project_name)
            and location is not None
            and Path(location).resolve() == project_dir.resolve()
        ):
            excluded += 1
            continue
        requirements.append(f"{package['name']}=={package['version']}")
    if excluded != 1:
        raise ValueError("Expected exactly one editable install of the current project")
    return sorted(requirements)


def main():
    project_dir = Path.cwd()
    with (project_dir / "pyproject.toml").open("rb") as project_file:
        project_name = tomllib.load(project_file)["project"]["name"]
    packages = json.loads(subprocess.check_output(
        [sys.executable, "-m", "pip", "list", "--format=json"], text=True,
    ))
    requirements = requirements_for(packages, project_name, project_dir)
    print(f"Auditing {len(requirements)} installed packages; excluding editable {project_name}", flush=True)
    with tempfile.TemporaryDirectory(prefix="scanforge-audit-") as directory:
        requirements_path = Path(directory) / "requirements.txt"
        requirements_path.write_text("\n".join(requirements) + "\n", encoding="utf-8")
        # Audit exact installed versions without resolving the project's dependencies
        # again. Strict mode still rejects unknown third-party packages.
        return subprocess.call([
            sys.executable, "-m", "pip_audit", "--strict", "--no-deps",
            "--disable-pip", "--requirement", str(requirements_path),
        ])


if __name__ == "__main__":
    sys.exit(main())
