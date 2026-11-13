"""Regression checks for the executable GitHub Actions quality gate."""

import itertools
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest

import yaml


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"


class CiGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]

    def test_audits_are_blocking_and_threshold_is_preserved(self):
        for name in ("api", "worker", "web"):
            job = self.jobs[name]
            self.assertFalse(job.get("continue-on-error", False))
            audits = [step for step in job["steps"]
                      if step.get("name", "").startswith("Audit dependencies")]
            self.assertEqual(len(audits), 1)
            audit = audits[0]
            self.assertFalse(audit.get("continue-on-error", False))
            self.assertNotIn("if", audit)
            expected = ("npm audit --audit-level=high" if name == "web"
                        else "python ../../scripts/audit_python_dependencies.py")
            self.assertEqual(audit["run"], expected)
            for step in job["steps"]:
                self.assertFalse(step.get("continue-on-error", False))

    def test_sbom_requires_explicit_success_from_every_application_job(self):
        job = self.jobs["sbom"]
        self.assertEqual(set(job["needs"]), {"api", "worker", "web"})
        self.assertEqual(job["if"],
                         "success() && github.ref == 'refs/heads/main' && "
                         "needs.api.result == 'success' && "
                         "needs.worker.result == 'success' && "
                         "needs.web.result == 'success'")
        self.assertFalse(job.get("continue-on-error", False))

    def test_api_requires_real_worker_recovery(self):
        steps = self.jobs["api"]["steps"]
        recovery = [step for step in steps if step.get("name") == "Persisted worker recovery"]
        self.assertEqual(len(recovery), 1)
        step = recovery[0]
        self.assertNotIn("if", step)
        self.assertFalse(step.get("continue-on-error", False))
        self.assertIn("test_worker_recovery_postgres.py", step["run"])
        self.assertEqual(step["env"]["RECOVERY_REQUIRED"], "1")
        self.assertIn("RECOVERY_WORKER_PYTHON", step["env"])
        setup = next(item for item in steps if item.get("name") == "Prepare recovery services")
        self.assertLess(steps.index(setup), steps.index(step))
        self.assertIn("postgresql", setup["run"])
        self.assertIn("redis-server", setup["run"])
        self.assertIn("venv", setup["run"])

    def test_required_gate_rejects_failed_cancelled_or_skipped_jobs(self):
        job = self.jobs["required"]
        self.assertEqual(job["if"], "always()")
        self.assertEqual(set(job["needs"]), {"changes", "api", "worker", "web", "sbom"})
        step = job["steps"][0]
        for branch, status, target in itertools.product(
            ("main", "feature"), ("success", "failure", "cancelled", "skipped"),
            ("CHANGES", "API", "WORKER", "WEB", "SBOM"),
        ):
            env = dict(os.environ, GITHUB_REF=f"refs/heads/{branch}", ALL_EXPECTED="true",
                       CHANGES="success", API="success", WORKER="success", WEB="success",
                       SBOM="success", API_EXPECTED="true", WORKER_EXPECTED="true", WEB_EXPECTED="true")
            env[target] = status
            # Execute the actual workflow gate, not a reimplementation of its logic.
            script = step["run"].replace("python -", f"{shlex.quote(sys.executable)} -", 1)
            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
            allowed = status == "success" or (target == "SBOM" and branch != "main" and status == "skipped")
            with self.subTest(branch=branch, target=target, status=status):
                self.assertEqual(result.returncode, 0 if allowed else 1, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
