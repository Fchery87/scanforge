#!/usr/bin/env python3
"""Dependency-engine evaluation harness (#37, ADR-019).

Compares Trivy, OSV-Scanner and Grype (plus Syft as inventory) against the corpus in
``apps/worker/tests/fixtures/dependency_eval``.

Subcommands:

* ``plan``   write a results skeleton in which every engine/case cell is ``NOT RUN``.
* ``run``    execute the pinned scanner image against each case via the worker's contained runtime.
             Needs Docker and ``SCANNER_IMAGE``. It was written without a Docker host and has never
             been executed; treat its first run as a test of the harness as well as of the engines.
* ``render`` turn a results JSON into markdown tables. Cells that were not run print ``NOT RUN``.

Nothing in this file produces a result without running a scanner.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "apps" / "worker" / "tests" / "fixtures" / "dependency_eval"
WORKER_DIR = ROOT / "apps" / "worker"
ENGINES = ("trivy", "osv", "grype", "syft")
DEFAULT_RESULTS = ROOT / "docs" / "reviews" / "2026-11-dependency-engine-evaluation-results.json"
NOT_RUN = "NOT RUN"
_WORKSPACE_PREFIX = "/workspace/source/"


class EnvironmentNotAvailable(RuntimeError):
    """Raised when a real-scanner run is requested without Docker or the pinned image."""


@dataclass(frozen=True)
class Observation:
    name: str
    version: str
    advisory_ids: tuple[str, ...] = ()
    manifest: str | None = None
    ecosystem: str | None = None
    fixed_versions: tuple[str, ...] = field(default_factory=tuple)


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def normalize_path(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(_WORKSPACE_PREFIX):
        path = path[len(_WORKSPACE_PREFIX) :]
    return path.lstrip("/") or None


def _first_location(locations) -> str | None:
    for location in locations or []:
        path = normalize_path((location or {}).get("path"))
        if path:
            return path
    return None


def _extract_trivy(raw: dict) -> list[Observation]:
    out = []
    for result in raw.get("Results") or []:
        manifest = normalize_path(result.get("Target"))
        for vuln in result.get("Vulnerabilities") or []:
            fixed = vuln.get("FixedVersion")
            out.append(
                Observation(
                    name=normalize_name(vuln.get("PkgName", "")),
                    version=vuln.get("InstalledVersion", ""),
                    advisory_ids=(vuln["VulnerabilityID"],) if vuln.get("VulnerabilityID") else (),
                    manifest=manifest,
                    ecosystem=result.get("Type"),
                    fixed_versions=(fixed,) if fixed else (),
                )
            )
    return out


def _extract_osv(raw: dict) -> list[Observation]:
    out = []
    for result in raw.get("results") or []:
        manifest = normalize_path((result.get("source") or {}).get("path"))
        for entry in result.get("packages") or []:
            package = entry.get("package") or {}
            for vuln in entry.get("vulnerabilities") or []:
                ids = tuple([vuln["id"], *(vuln.get("aliases") or [])]) if vuln.get("id") else ()
                out.append(
                    Observation(
                        name=normalize_name(package.get("name", "")),
                        version=package.get("version", ""),
                        advisory_ids=ids,
                        manifest=manifest,
                        ecosystem=package.get("ecosystem"),
                    )
                )
    return out


def _extract_grype(raw: dict) -> list[Observation]:
    out = []
    for match in raw.get("matches") or []:
        vuln = match.get("vulnerability") or {}
        artifact = match.get("artifact") or {}
        out.append(
            Observation(
                name=normalize_name(artifact.get("name", "")),
                version=artifact.get("version", ""),
                advisory_ids=(vuln["id"],) if vuln.get("id") else (),
                manifest=_first_location(artifact.get("locations")),
                ecosystem=artifact.get("type"),
                fixed_versions=tuple((vuln.get("fix") or {}).get("versions") or ()),
            )
        )
    return out


def _extract_syft(raw: dict) -> list[Observation]:
    return [
        Observation(
            name=normalize_name(artifact.get("name", "")),
            version=artifact.get("version", ""),
            manifest=_first_location(artifact.get("locations")),
            ecosystem=artifact.get("type"),
        )
        for artifact in raw.get("artifacts") or []
    ]


_EXTRACTORS = {"trivy": _extract_trivy, "osv": _extract_osv, "grype": _extract_grype, "syft": _extract_syft}


def extract_observations(engine: str, raw: dict) -> list[Observation]:
    return _EXTRACTORS[engine](raw)


def _matches(obs: Observation, expected: dict) -> bool:
    if obs.name != normalize_name(expected["name"]) or obs.version != expected["version"]:
        return False
    return obs.manifest is None or obs.manifest == expected["manifest"]


def score_case(case: dict, observations: list[Observation]) -> dict:
    """Score vulnerability reports for one case. Advisory IDs are informational; match is package@version."""
    vulnerabilities = observations
    expected = case.get("expect_vulnerable", [])
    clean = case.get("expect_clean", [])
    true_positives = sum(1 for e in expected if any(_matches(o, e) for o in vulnerabilities))
    false_positives = sum(1 for c in clean if any(_matches(o, c) for o in vulnerabilities))
    known = {(normalize_name(e["name"]), e["version"]) for e in [*expected, *clean]}
    unlisted = sorted({f"{o.name}@{o.version}" for o in vulnerabilities if (o.name, o.version) not in known})
    return {
        "true_positives": true_positives,
        "false_negatives": len(expected) - true_positives,
        "false_positives": false_positives,
        "unlisted_for_review": unlisted,
        "manifest_path_reported": bool(vulnerabilities) and all(o.manifest for o in vulnerabilities),
        "advisory_ids": sorted({i for o in vulnerabilities for i in o.advisory_ids}),
        "fixed_versions_reported": any(o.fixed_versions for o in vulnerabilities),
        "ecosystems_reported": sorted({o.ecosystem for o in vulnerabilities if o.ecosystem}),
    }


def score_inventory(case: dict, observations: list[Observation]) -> dict:
    """Score Syft-style inventory: every pinned package in the case should be listed."""
    pins = [*case.get("expect_vulnerable", []), *case.get("expect_clean", [])]
    found = sum(1 for pin in pins if any(_matches(o, pin) for o in observations))
    return {
        "pins_expected": len(pins),
        "pins_found": found,
        "pins_missing": len(pins) - found,
        "manifest_path_reported": bool(observations) and all(o.manifest for o in observations),
    }


def plan_results(ground_truth: dict) -> dict:
    return {
        "schema_version": "2026-11-dependency-eval-results.v1",
        "status": NOT_RUN,
        "note": "Skeleton only. No scanner has been executed; every cell is NOT RUN.",
        "engines": {
            engine: {case["id"]: {"status": NOT_RUN} for case in ground_truth["cases"]} for engine in ENGINES
        },
    }


def render_markdown(results: dict) -> str:
    lines = [f"Overall status: **{results.get('status', NOT_RUN)}**", ""]
    for engine, per_case in results["engines"].items():
        lines += [f"### {engine}", "", "| Case | Status | TP | FN | FP | Manifest path | Fixed versions | Duration ms | Notes |", "|---|---|---|---|---|---|---|---|---|"]
        for case_id, cell in per_case.items():
            if cell["status"] != "RUN OK":
                lines.append(f"| {case_id} | {cell['status']} | - | - | - | - | - | - | {cell.get('error', '')} |")
                continue
            if engine == "syft":
                lines.append(
                    f"| {case_id} | RUN OK | found {cell['pins_found']}/{cell['pins_expected']} | - | - | "
                    f"{cell['manifest_path_reported']} | - | {cell.get('duration_ms', '?')} | inventory |"
                )
                continue
            review = ", ".join(cell["unlisted_for_review"]) or "-"
            lines.append(
                f"| {case_id} | RUN OK | {cell['true_positives']} | {cell['false_negatives']} | "
                f"{cell['false_positives']} | {cell['manifest_path_reported']} | {cell['fixed_versions_reported']} | "
                f"{cell.get('duration_ms', '?')} | unlisted: {review} |"
            )
        lines.append("")
    return "\n".join(lines)


def require_run_environment(env=None, which=shutil.which) -> None:
    env = os.environ if env is None else env
    if not which("docker"):
        raise EnvironmentNotAvailable("docker is not on PATH; real-scanner runs need a Docker host")
    if not env.get("SCANNER_IMAGE"):
        raise EnvironmentNotAvailable("SCANNER_IMAGE (digest-pinned) must be set for real-scanner runs")


def _run_cell(engine: str, case: dict, results_dir: Path) -> dict:  # pragma: no cover - needs Docker
    sys.path.insert(0, str(WORKER_DIR))
    from app.runtime.base import build_scan_runtime
    from app.scanners.registry import SCANNER_REGISTRY

    adapter = SCANNER_REGISTRY[engine].adapter_factory()
    source = CORPUS / "cases" / case["id"]
    started = time.perf_counter()
    result = adapter.run_contained(source, build_scan_runtime())
    duration_ms = int((time.perf_counter() - started) * 1000)
    raw_path = results_dir / f"{engine}--{case['id']}.json"
    raw_path.write_text(json.dumps(result.raw_output, indent=2))
    cell = {"status": "RUN OK" if result.success else "RUN FAILED", "duration_ms": duration_ms, "raw_output": raw_path.name}
    if not result.success:
        cell["error"] = result.error
        return cell
    observations = extract_observations(engine, result.raw_output)
    cell.update(score_inventory(case, observations) if engine == "syft" else score_case(case, observations))
    # Peak memory and offline behaviour are not captured here: sample `docker stats` /
    # cgroup memory.peak during the run and confirm --network=none by hand.
    return cell


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "run", "render"])
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)
    ground_truth = json.loads((CORPUS / "ground_truth.json").read_text())

    if args.command == "plan":
        args.results.write_text(json.dumps(plan_results(ground_truth), indent=2) + "\n")
        print(f"wrote {args.results} (all cells {NOT_RUN})")
        return 0
    if args.command == "render":
        print(render_markdown(json.loads(args.results.read_text())))
        return 0

    try:
        require_run_environment()
    except EnvironmentNotAvailable as exc:
        print(f"{NOT_RUN}: {exc}", file=sys.stderr)
        return 2
    results = plan_results(ground_truth)
    raw_dir = args.results.parent / (args.results.stem + "-raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    for engine in ENGINES:
        for case in ground_truth["cases"]:
            results["engines"][engine][case["id"]] = _run_cell(engine, case, raw_dir)
    statuses = {c["status"] for per in results["engines"].values() for c in per.values()}
    results["status"] = "RUN OK" if statuses == {"RUN OK"} else "RUN PARTIAL"
    results["note"] = "Real scanner output. Peak memory and offline behaviour must be recorded by hand."
    args.results.write_text(json.dumps(results, indent=2) + "\n")
    print(render_markdown(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
