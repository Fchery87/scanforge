"""Regression tests for the CI dependency inventory and audit failure handling."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_python_dependencies as audit


class AuditDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path("/tmp/project")
        self.project = {
            "name": "local-project", "version": "0.1.0",
            "editable_project_location": str(self.project_dir),
        }

    def test_excludes_only_current_editable_project(self):
        packages = [
            self.project,
            {"name": "runtime", "version": "1.0"},
            {"name": "dev", "version": "2.0"},
            {"name": "transitive", "version": "3.0"},
            {"name": "unknown-third-party", "version": "4.0"},
            {"name": "editable-third-party", "version": "5.0",
             "editable_project_location": "/tmp/third-party"},
        ]
        self.assertEqual(
            audit.requirements_for(packages, "Local_Project", self.project_dir),
            ["dev==2.0", "editable-third-party==5.0", "runtime==1.0",
             "transitive==3.0", "unknown-third-party==4.0"],
        )

    def test_fails_if_local_project_is_missing_not_editable_or_elsewhere(self):
        for packages in (
            [],
            [{"name": "local-project", "version": "0.1.0"}],
            [{**self.project, "editable_project_location": "/tmp/elsewhere"}],
            [self.project, self.project],
        ):
            with self.subTest(packages=packages), self.assertRaises(ValueError):
                audit.requirements_for(packages, "local-project", self.project_dir)

    def test_keeps_same_name_at_other_location(self):
        other = {**self.project, "editable_project_location": "/tmp/elsewhere"}
        self.assertEqual(
            audit.requirements_for([self.project, other], "local-project", self.project_dir),
            ["local-project==0.1.0"],
        )

    def test_keeps_noneditable_same_name(self):
        other = {"name": "local-project", "version": "0.2.0"}
        self.assertEqual(
            audit.requirements_for([self.project, other], "local-project", self.project_dir),
            ["local-project==0.2.0"],
        )

    def test_inventory_failure_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            project_dir = Path(directory)
            (project_dir / "pyproject.toml").write_text('[project]\nname = "local-project"\n')
            with (
                patch.object(audit.Path, "cwd", return_value=project_dir),
                patch.object(audit.subprocess, "check_output", side_effect=RuntimeError("pip failed")),
                patch.object(audit.subprocess, "call") as run_audit,
                self.assertRaisesRegex(RuntimeError, "pip failed"),
            ):
                audit.main()
            run_audit.assert_not_called()

    def test_audits_pinned_inventory_and_propagates_exit_status(self):
        for status in (0, 1, 2):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                project_dir = Path(directory)
                (project_dir / "pyproject.toml").write_text('[project]\nname = "local-project"\n')
                packages = [
                    {**self.project, "editable_project_location": directory},
                    {"name": "third-party", "version": "1.2.3"},
                ]

                def run_audit(command, status=status):
                    self.assertEqual(command[:7], [
                        audit.sys.executable, "-m", "pip_audit", "--strict",
                        "--no-deps", "--disable-pip", "--requirement",
                    ])
                    self.assertEqual(Path(command[7]).read_text(), "third-party==1.2.3\n")
                    return status

                with (
                    patch.object(audit.Path, "cwd", return_value=project_dir),
                    patch.object(audit.subprocess, "check_output", return_value=json.dumps(packages)),
                    patch.object(audit.subprocess, "call", side_effect=run_audit),
                ):
                    self.assertEqual(audit.main(), status)


if __name__ == "__main__":
    unittest.main()
