#!/usr/bin/env python3
"""Run local checks and require deployment evidence before beta approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_CHECKS = (
    "postgres-full-suite", "migration-empty-and-upgrade", "staging-deployment",
    "upstash-recovery", "github-triggers-and-check", "authenticated-browser",
    "canary-boundaries", "operational-drills", "monitoring-alerts", "beta-load",
    "scanner-image-offline-assets",
)


@dataclass(frozen=True)
class Check:
    name: str
    directory: str
    command: tuple[str, ...]
    environment: tuple[tuple[str, str], ...] = ()


def local_checks() -> list[Check]:
    return [
        Check("api-lint", "apps/api", (".venv/bin/ruff", "check", "app")),
        Check("worker-lint", "apps/worker", (".venv/bin/ruff", "check", "app")),
        Check("generated-contracts", ".", (sys.executable, str(Path(__file__).resolve()), "--contracts-only")),
        Check("migration-single-head", "apps/api", (".venv/bin/python", "-c",
            "from alembic.config import Config; from alembic.script import ScriptDirectory; "
            "heads = ScriptDirectory.from_config(Config('alembic.ini')).get_heads(); "
            "print(heads); import sys; sys.exit(0 if len(heads) == 1 else 1)")),
        Check("api-tests", "apps/api", (".venv/bin/python", "-m", "pytest", "tests", "-q")),
        Check("worker-tests", "apps/worker", (".venv/bin/python", "-m", "pytest", "tests", "-q")),
        Check("web-lint", "apps/web", ("npm", "run", "lint")),
        Check("web-types", "apps/web", ("npx", "--no-install", "tsc", "--noEmit")),
        Check("web-node-tests", "apps/web", ("npm", "run", "test:node")),
        Check("web-component-tests", "apps/web", ("npm", "run", "test:vitest", "--", "--maxWorkers=1")),
        Check("web-build", "apps/web", ("npm", "run", "build", "--", "--webpack")),
        Check("api-dependency-audit", "apps/api", (".venv/bin/python", "-m", "pip_audit", "--local", "--skip-editable")),
        Check("worker-dependency-audit", "apps/worker", (".venv/bin/python", "-m", "pip_audit", "--local", "--skip-editable")),
        Check("web-dependency-audit", "apps/web", ("npm", "audit", "--audit-level=high")),
    ]


def run_check(check: Check, output: Path, *, reject_skips: bool = False) -> dict:
    environment = dict(os.environ)
    for name in ("TEST_POSTGRES_URL", "REDIS_URL", "SCANFORGE_LIVE_DOCKER"):
        environment.pop(name, None)
    environment.update(check.environment)
    log = output / f"{check.name}.log"
    print(f"Running {check.name}", flush=True)
    try:
        with log.open("w") as stream:
            result = subprocess.run(check.command, cwd=ROOT / check.directory, env=environment,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=2400, check=False)
        passed = result.returncode == 0
        detail = f"exit {result.returncode}"
        if reject_skips and re.search(r"\b\d+ skipped\b", log.read_text()):
            passed = False
            detail = "integration suite skipped tests"
    except (OSError, subprocess.TimeoutExpired) as error:
        passed = False
        detail = type(error).__name__
    print(f"{check.name}: {'passed' if passed else 'failed'} ({detail})", flush=True)
    return {"name": check.name, "status": "passed" if passed else "failed", "detail": detail,
            "log": log.name, "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None}


def validate_evidence(directory: Path | None, name: str, sha: str) -> dict:
    try:
        if directory is None:
            raise ValueError("evidence directory not supplied")
        receipt = json.loads((directory / f"{name}.json").read_text())
        if not isinstance(receipt, dict):
            raise ValueError("receipt must be a JSON object")
        if receipt.get("status") != "passed" or receipt.get("commit_sha") != sha:
            raise ValueError("receipt must pass for the current commit")
        if not isinstance(receipt.get("observed_at"), str):
            raise ValueError("observation time is required")
        observed = datetime.fromisoformat(receipt["observed_at"].replace("Z", "+00:00"))
        if observed.tzinfo is None or observed > datetime.now(timezone.utc):
            raise ValueError("invalid observation time")
        if not receipt.get("environment") or not receipt.get("operator"):
            raise ValueError("environment and operator are required")
        artifacts = receipt.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("evidence artifacts are required")
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
                raise ValueError("artifact needs a relative path and SHA-256 checksum")
            path = (directory / artifact["path"]).resolve()
            if not path.is_relative_to(directory.resolve()) or not path.is_file():
                raise ValueError("artifact must be a file inside the evidence directory")
            if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                raise ValueError("artifact checksum mismatch")
        return {"name": name, "status": "passed", "detail": "operator receipt and artifact hashes validated"}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"name": name, "status": "unverified", "detail": str(error)}


def verify_contracts() -> int:
    environment = dict(os.environ)
    environment["DATABASE_URL"] = "postgresql+asyncpg://dummy:dummy@localhost/dummy"
    environment["APP_ENV"] = "test"
    command = (str(ROOT / "apps/api/.venv/bin/python"), "-c",
               "import json; from app.main import app; print(json.dumps(app.openapi()))")
    try:
        emitted = subprocess.check_output(command, cwd=ROOT / "apps/api", env=environment, timeout=120, text=True)
        schema = json.loads(emitted)
        if schema != json.loads((ROOT / "apps/api/openapi.json").read_text()):
            raise ValueError("apps/api/openapi.json differs from the application contract")
        with tempfile.TemporaryDirectory(prefix="scanforge-contracts-") as directory:
            schema_path = Path(directory) / "openapi.json"
            schema_path.write_text((ROOT / "apps/api/openapi.json").read_text())
            types_path = Path(directory) / "api-types.ts"
            subprocess.run(("npx", "--no-install", "openapi-typescript", str(schema_path), "--output", str(types_path)),
                           cwd=ROOT / "apps/web", env=environment, check=True, timeout=120)
            if types_path.read_bytes() != (ROOT / "apps/web/lib/api-types.ts").read_bytes():
                raise ValueError("apps/web/lib/api-types.ts differs from the generated contract")
        print("Generated API schema and web types match the application contract")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Contract verification failed: {error}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=("local", "release"), default="release")
    parser.add_argument("--output", type=Path, default=Path("/tmp/scanforge-private-beta-gate"))
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    if args.contracts_only:
        return verify_contracts()
    args.output.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(("git", "status", "--porcelain"), cwd=ROOT, text=True).strip())
    checks = [run_check(check, args.output) for check in local_checks()]
    integrations = (
        ("postgres-completion", "TEST_POSTGRES_URL", Check("postgres-completion", "apps/api",
            (".venv/bin/python", "-m", "pytest", "tests/test_completion_postgres_beta.py", "-q"))),
        ("native-redis-recovery", "REDIS_URL", Check("native-redis-recovery", "apps/worker",
            (".venv/bin/python", "-m", "pytest", "tests/test_queue_native_beta.py", "-q"))),
        ("live-docker", "SCANFORGE_LIVE_DOCKER", Check("live-docker", "apps/worker",
            (".venv/bin/python", "-m", "pytest", "tests/test_live_docker_beta.py", "-q"))),
    )
    for name, variable, check in integrations:
        enabled = bool(os.environ.get(variable))
        if variable == "SCANFORGE_LIVE_DOCKER":
            enabled = os.environ.get(variable) == "1" and bool(
                re.fullmatch(r".+@sha256:[0-9a-fA-F]{64}", os.environ.get("SCANNER_IMAGE", ""))
            )
        if enabled:
            check = Check(check.name, check.directory, check.command, ((variable, os.environ[variable]),))
            checks.append(run_check(check, args.output, reject_skips=True))
        else:
            checks.append({"name": name, "status": "unverified", "detail": f"{variable} not configured"})
    checks.extend(validate_evidence(args.evidence_dir, name, sha) for name in EXTERNAL_CHECKS)
    checks.append({"name": "committed-source", "status": "unverified" if dirty else "passed",
                   "detail": "working tree has uncommitted changes" if dirty else sha})
    release_ready = all(check["status"] == "passed" for check in checks)
    failed = any(check["status"] == "failed" for check in checks)
    report = {"contract_version": 1, "mode": args.mode, "commit_sha": sha, "dirty": dirty,
              "observed_at": datetime.now(timezone.utc).isoformat(), "release_ready": release_ready, "checks": checks}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for check in checks:
        if check["status"] == "unverified":
            print(f"Unverified {check['name']}: {check['detail']}")
    print(f"Report: {args.output / 'report.json'}")
    print(f"Release ready: {release_ready}")
    return int(failed or (args.mode == "release" and not release_ready))


if __name__ == "__main__":
    raise SystemExit(main())
