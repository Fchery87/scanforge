"""Tests for the dependency-engine evaluation harness (#37, ADR-019).

The reports below are SYNTHETIC: hand-written to match each tool's documented JSON shape so the
extraction and scoring logic can be exercised without a Docker host. They are not scanner output and
no number derived from them may be recorded as an evaluation result.
"""

import json
import unittest
from pathlib import Path

import evaluate_dependency_engines as ev

CORPUS = Path(__file__).resolve().parents[1] / "apps" / "worker" / "tests" / "fixtures" / "dependency_eval"
GROUND_TRUTH = json.loads((CORPUS / "ground_truth.json").read_text())

TRIVY_SYNTHETIC = {
    "Results": [
        {
            "Target": "package-lock.json",
            "Class": "lang-pkgs",
            "Type": "npm",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2021-23337",
                    "PkgName": "lodash",
                    "InstalledVersion": "4.17.15",
                    "FixedVersion": "4.17.21",
                }
            ],
        }
    ]
}
OSV_SYNTHETIC = {
    "results": [
        {
            "source": {"path": "/workspace/source/package-lock.json", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "lodash", "version": "4.17.15", "ecosystem": "npm"},
                    "vulnerabilities": [{"id": "GHSA-35jh-r3h4-6jhm", "aliases": ["CVE-2021-23337"]}],
                }
            ],
        }
    ]
}
GRYPE_SYNTHETIC = {
    "matches": [
        {
            "vulnerability": {"id": "GHSA-35jh-r3h4-6jhm", "fix": {"versions": ["4.17.21"], "state": "fixed"}},
            "artifact": {
                "name": "lodash",
                "version": "4.17.15",
                "type": "npm",
                "locations": [{"path": "/package-lock.json"}],
            },
        }
    ]
}
SYFT_SYNTHETIC = {
    "artifacts": [
        {"name": "lodash", "version": "4.17.15", "type": "npm", "locations": [{"path": "/package-lock.json"}]}
    ]
}


class PlanTests(unittest.TestCase):
    def test_plan_marks_every_engine_and_case_not_run(self):
        results = ev.plan_results(GROUND_TRUTH)

        self.assertEqual(results["status"], "NOT RUN")
        cells = [cell for per_case in results["engines"].values() for cell in per_case.values()]
        self.assertGreater(len(cells), 0)
        self.assertEqual({cell["status"] for cell in cells}, {"NOT RUN"})
        for cell in cells:
            self.assertNotIn("true_positives", cell)

    def test_plan_covers_every_engine_against_every_case(self):
        results = ev.plan_results(GROUND_TRUTH)

        case_ids = {case["id"] for case in GROUND_TRUTH["cases"]}
        self.assertEqual(set(results["engines"]), {"trivy", "osv", "grype", "syft"})
        for per_case in results["engines"].values():
            self.assertEqual(set(per_case), case_ids)

    def test_rendered_plan_contains_no_numbers_for_unrun_engines(self):
        text = ev.render_markdown(ev.plan_results(GROUND_TRUTH))

        self.assertIn("NOT RUN", text)
        self.assertNotIn("RUN OK", text)


class ExtractionTests(unittest.TestCase):
    def test_trivy_reports_package_advisory_manifest_and_fixed_version(self):
        (obs,) = ev.extract_observations("trivy", TRIVY_SYNTHETIC)

        self.assertEqual((obs.name, obs.version, obs.manifest), ("lodash", "4.17.15", "package-lock.json"))
        self.assertEqual(obs.advisory_ids, ("CVE-2021-23337",))
        self.assertEqual(obs.fixed_versions, ("4.17.21",))

    def test_osv_strips_workspace_prefix_and_keeps_aliases(self):
        (obs,) = ev.extract_observations("osv", OSV_SYNTHETIC)

        self.assertEqual(obs.manifest, "package-lock.json")
        self.assertEqual(obs.advisory_ids, ("GHSA-35jh-r3h4-6jhm", "CVE-2021-23337"))
        self.assertEqual(obs.fixed_versions, ())

    def test_grype_strips_leading_slash_from_location(self):
        (obs,) = ev.extract_observations("grype", GRYPE_SYNTHETIC)

        self.assertEqual(obs.manifest, "package-lock.json")
        self.assertEqual(obs.fixed_versions, ("4.17.21",))

    def test_syft_inventory_has_no_advisories(self):
        (obs,) = ev.extract_observations("syft", SYFT_SYNTHETIC)

        self.assertEqual(obs.advisory_ids, ())
        self.assertEqual((obs.name, obs.version), ("lodash", "4.17.15"))

    def test_pypi_names_are_normalized(self):
        report = {
            "matches": [
                {
                    "vulnerability": {"id": "GHSA-8q59-q68h-6hv4", "fix": {"versions": []}},
                    "artifact": {"name": "PyYAML", "version": "5.3.1", "locations": [{"path": "/requirements.txt"}]},
                }
            ]
        }
        (obs,) = ev.extract_observations("grype", report)

        self.assertEqual(obs.name, "pyyaml")


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.case = next(c for c in GROUND_TRUTH["cases"] if c["id"] == "npm-vulnerable")

    def test_missing_expected_vulnerability_is_a_false_negative(self):
        score = ev.score_case(self.case, ev.extract_observations("trivy", TRIVY_SYNTHETIC))

        self.assertEqual(score["true_positives"], 1)
        self.assertEqual(score["false_negatives"], 1)
        self.assertEqual(score["false_positives"], 0)

    def test_hit_on_clean_pin_is_a_false_positive(self):
        clean = next(c for c in GROUND_TRUTH["cases"] if c["id"] == "npm-clean")
        report = {
            "Results": [
                {
                    "Target": "package-lock.json",
                    "Vulnerabilities": [
                        {"VulnerabilityID": "CVE-0000-0000", "PkgName": "lodash", "InstalledVersion": "4.17.21"}
                    ],
                }
            ]
        }
        score = ev.score_case(clean, ev.extract_observations("trivy", report))

        self.assertEqual(score["false_positives"], 1)

    def test_monorepo_requires_one_hit_per_manifest_path(self):
        case = next(c for c in GROUND_TRUTH["cases"] if c["id"] == "monorepo-duplicate")
        one_manifest_only = {
            "Results": [
                {
                    "Target": "packages/a/package-lock.json",
                    "Vulnerabilities": [{"VulnerabilityID": "X", "PkgName": "lodash", "InstalledVersion": "4.17.15"}],
                }
            ]
        }
        score = ev.score_case(case, ev.extract_observations("trivy", one_manifest_only))

        self.assertEqual(score["true_positives"], 1)
        self.assertEqual(score["false_negatives"], 1)

    def test_engine_that_reports_no_manifest_is_matched_by_package_and_flagged(self):
        report = {"matches": [{"vulnerability": {"id": "X"}, "artifact": {"name": "lodash", "version": "4.17.15"}}]}
        score = ev.score_case(self.case, ev.extract_observations("grype", report))

        self.assertEqual(score["true_positives"], 1)
        self.assertFalse(score["manifest_path_reported"])

    def test_vulnerability_not_in_ground_truth_is_listed_for_manual_review(self):
        report = {
            "Results": [
                {
                    "Target": "package-lock.json",
                    "Vulnerabilities": [{"VulnerabilityID": "X", "PkgName": "left-pad", "InstalledVersion": "1.0.0"}],
                }
            ]
        }
        score = ev.score_case(self.case, ev.extract_observations("trivy", report))

        self.assertEqual(score["unlisted_for_review"], ["left-pad@1.0.0"])


class CorpusIntegrityTests(unittest.TestCase):
    def test_every_ground_truth_pin_is_present_in_its_manifest(self):
        for case in GROUND_TRUTH["cases"]:
            for pin in [*case["expect_vulnerable"], *case["expect_clean"]]:
                manifest = (CORPUS / "cases" / case["id"] / pin["manifest"]).read_text().lower()
                self.assertIn(pin["name"].lower(), manifest, (case["id"], pin))
                self.assertIn(pin["version"], manifest, (case["id"], pin))

    def test_every_manifest_in_a_case_is_declared_as_an_input(self):
        names = {"package-lock.json", "requirements.txt", "poetry.lock"}
        for case in GROUND_TRUTH["cases"]:
            on_disk = {
                str(p.relative_to(CORPUS / "cases" / case["id"]))
                for p in (CORPUS / "cases" / case["id"]).rglob("*")
                if p.name in names
            }
            self.assertEqual(on_disk, set(case["inputs"]), case["id"])


class RunGuardTests(unittest.TestCase):
    def test_run_refuses_without_docker_or_scanner_image(self):
        with self.assertRaises(ev.EnvironmentNotAvailable):
            ev.require_run_environment(env={}, which=lambda _name: None)

    def test_run_requires_scanner_image_even_when_docker_exists(self):
        with self.assertRaises(ev.EnvironmentNotAvailable):
            ev.require_run_environment(env={}, which=lambda _name: "/usr/bin/docker")


if __name__ == "__main__":
    unittest.main()
