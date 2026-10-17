#!/usr/bin/env python3
"""Verify test inventory, integration environment gates, and disposable fixtures (M00)."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
WORKER_DIR = ROOT / "apps" / "worker"
WEB_DIR = ROOT / "apps" / "web"
API_PYTHON = API_DIR / ".venv" / "bin" / "python"
WORKER_PYTHON = WORKER_DIR / ".venv" / "bin" / "python"
API_ALEMBIC = API_DIR / ".venv" / "bin" / "alembic"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _find_pg_bin(name: str) -> str | None:
    direct = shutil.which(name)
    if direct:
        return direct
    for candidate in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}"), reverse=True):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


@contextlib.contextmanager
def disposable_postgres_cluster():
    """Start an isolated, disposable TCP PostgreSQL cluster and run alembic upgrade head."""
    initdb = _find_pg_bin("initdb")
    pg_ctl = _find_pg_bin("pg_ctl")
    createdb = _find_pg_bin("createdb")
    if not (initdb and pg_ctl and createdb):
        raise RuntimeError("PostgreSQL server binaries (initdb/pg_ctl/createdb) not available")

    temp_root = Path(tempfile.mkdtemp(prefix="scanforge-pg-fixture-"))
    pgdata = temp_root / "pgdata"
    sockdir = temp_root / "sock"
    sockdir.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    db_name = "scanforge_fixture"
    user = "scanforge_fixture_user"

    try:
        subprocess.run(
            [initdb, "-D", str(pgdata), "-U", user, "--auth=trust", "--no-instructions"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        opts = f"-F -p {port} -h 127.0.0.1 -k {sockdir}"
        subprocess.run(
            [pg_ctl, "-D", str(pgdata), "-l", str(temp_root / "postgres.log"), "-o", opts, "start"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            [createdb, "-h", "127.0.0.1", "-p", str(port), "-U", user, db_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        sync_url = f"postgresql://{user}@127.0.0.1:{port}/{db_name}"
        async_url = f"postgresql+asyncpg://{user}@127.0.0.1:{port}/{db_name}"
        env = dict(os.environ)
        env["DATABASE_URL"] = async_url
        env["PYTHONPATH"] = str(API_DIR)
        subprocess.run(
            [str(API_ALEMBIC), "-c", "alembic.ini", "upgrade", "head"],
            cwd=API_DIR,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        yield {"sync_url": sync_url, "async_url": async_url, "port": port, "pgdata": str(pgdata)}
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(pgdata), "-m", "immediate", "stop"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(temp_root, ignore_errors=True)


@contextlib.contextmanager
def disposable_redis_server():
    """Start an isolated, disposable native Redis server on a free localhost port."""
    redis_server = shutil.which("redis-server")
    if not redis_server:
        raise RuntimeError("redis-server binary is not installed")
    temp_root = Path(tempfile.mkdtemp(prefix="scanforge-redis-fixture-"))
    port = _free_port()
    proc = subprocess.Popen(
        [
            redis_server,
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--dir",
            str(temp_root),
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    redis_url = f"redis://127.0.0.1:{port}/0"
    try:
        deadline = time.time() + 5.0
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.05)
        else:
            raise RuntimeError("disposable redis-server did not start in time")
        yield {"redis_url": redis_url, "port": port}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(temp_root, ignore_errors=True)


@contextlib.contextmanager
def disposable_s3_server():
    """Start a lightweight S3-compatible disposable object store supporting PUT/GET/HEAD/DELETE/List."""
    store: dict[tuple[str, str], dict] = {}
    lock = threading.Lock()

    class S3Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def _parse_bucket_key(self) -> tuple[str, str]:
            parsed = urlparse(self.path)
            parts = [unquote(p) for p in parsed.path.lstrip("/").split("/", 1)]
            bucket = parts[0] if parts else ""
            key = parts[1] if len(parts) > 1 else ""
            return bucket, key

        def do_PUT(self):
            bucket, key = self._parse_bucket_key()
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            if not key:
                self.send_response(200)
                self.end_headers()
                return
            etag = hashlib.md5(body).hexdigest()  # noqa: S324
            sha256 = hashlib.sha256(body).hexdigest()
            with lock:
                store[(bucket, key)] = {
                    "body": body,
                    "content_type": self.headers.get("Content-Type", "application/octet-stream"),
                    "etag": f'"{etag}"',
                    "sha256": sha256,
                    "size": len(body),
                }
            self.send_response(200)
            self.send_header("ETag", f'"{etag}"')
            self.end_headers()

        def do_HEAD(self):
            bucket, key = self._parse_bucket_key()
            with lock:
                obj = store.get((bucket, key))
            if obj is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", obj["content_type"])
            self.send_header("Content-Length", str(obj["size"]))
            self.send_header("ETag", obj["etag"])
            self.send_header("x-amz-meta-sha256", obj["sha256"])
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            bucket, key = self._parse_bucket_key()
            if not key:
                qs = parse_qs(parsed.query)
                prefix = qs.get("prefix", [""])[0]
                with lock:
                    keys = [k for (b, k) in sorted(store.keys()) if b == bucket and k.startswith(prefix)]
                contents = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in keys)
                xml = (
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    f"<ListBucketResult><Name>{bucket}</Name>{contents}</ListBucketResult>"
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/xml")
                self.send_header("Content-Length", str(len(xml)))
                self.end_headers()
                self.wfile.write(xml)
                return
            with lock:
                obj = store.get((bucket, key))
            if obj is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", obj["content_type"])
            self.send_header("Content-Length", str(obj["size"]))
            self.send_header("ETag", obj["etag"])
            self.end_headers()
            self.wfile.write(obj["body"])

        def do_DELETE(self):
            bucket, key = self._parse_bucket_key()
            with lock:
                store.pop((bucket, key), None)
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), S3Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield {
            "endpoint": f"http://127.0.0.1:{port}",
            "bucket": "scanforge-test-artifacts",
            "access_key_id": "scanforge_test_key",
            "secret_access_key": "scanforge_test_secret",
            "store": store,
        }
    finally:
        server.shutdown()
        server.server_close()


def inspect_gate_inventory() -> dict:
    """Compare scripts/private_beta_gate.py references against real repository test files."""
    gate_path = ROOT / "scripts" / "private_beta_gate.py"
    gate_source = gate_path.read_text()
    referenced_tests = re.findall(r"tests/[A-Za-z0-9_./-]+\.py", gate_source)
    missing_files = []
    existing_files = []
    for rel in sorted(set(referenced_tests)):
        api_candidate = API_DIR / rel
        worker_candidate = WORKER_DIR / rel
        if api_candidate.exists() or worker_candidate.exists():
            existing_files.append(rel)
        else:
            missing_files.append(rel)

    env_gated_tests = []
    for suite_name, base_dir in (("api", API_DIR / "tests"), ("worker", WORKER_DIR / "tests")):
        for path in sorted(base_dir.glob("test_*.py")):
            text = path.read_text()
            env_vars = sorted(set(re.findall(r'os\.(?:getenv|environ\.get)\(\s*["\']([A-Z0-9_]+)["\']', text)))
            if "pytest.skip" in text or "skipif" in text:
                env_gated_tests.append(
                    {
                        "suite": suite_name,
                        "file": str(path.relative_to(ROOT)),
                        "env_vars": env_vars,
                    }
                )

    return {
        "gate_referenced_tests": existing_files,
        "gate_missing_referenced_tests": missing_files,
        "env_gated_tests": env_gated_tests,
    }


def run_disposable_fixture_verification() -> dict:
    """Verify R04 PostgreSQL completion and Redis stream recovery against disposable fixtures."""
    results: dict[str, dict] = {}

    with disposable_postgres_cluster() as pg:
        env = dict(os.environ)
        env["R04_POSTGRES_URL"] = pg["async_url"]
        env["R09_POSTGRES_URL"] = pg["async_url"]
        env["R05_POSTGRES_URL"] = pg["async_url"]
        env["DATABASE_URL"] = pg["async_url"]
        env["PYTHONPATH"] = str(API_DIR)
        cmd = [
            str(API_PYTHON),
            "-m",
            "pytest",
            "tests/test_r04_postgres_completion_red.py",
            "-q",
            "-rs",
        ]
        proc = subprocess.run(cmd, cwd=API_DIR, env=env, capture_output=True, text=True, timeout=180, check=False)
        skipped = bool(re.search(r"\b\d+ skipped\b", proc.stdout))
        results["r04_postgres_completion"] = {
            "returncode": proc.returncode,
            "skipped": skipped,
            "passed": proc.returncode == 0 and not skipped,
            "output": proc.stdout.strip(),
        }

    with disposable_redis_server() as rd:
        env = dict(os.environ)
        env["REDIS_URL"] = rd["redis_url"]
        env["PYTHONPATH"] = str(WORKER_DIR)
        cmd = [
            str(WORKER_PYTHON),
            "-m",
            "pytest",
            "tests/test_redis_stream_recovery_integration.py",
            "-q",
            "-rs",
        ]
        proc = subprocess.run(cmd, cwd=WORKER_DIR, env=env, capture_output=True, text=True, timeout=60, check=False)
        skipped = bool(re.search(r"\b\d+ skipped\b", proc.stdout))
        results["redis_stream_recovery"] = {
            "returncode": proc.returncode,
            "skipped": skipped,
            "passed": proc.returncode == 0 and not skipped,
            "output": proc.stdout.strip(),
        }

    with disposable_s3_server() as s3:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(API_DIR)
        probe_code = (
            "import urllib.request; "
            "from app.clients.r2 import R2Client; "
            f"c = R2Client(endpoint={s3['endpoint']!r}, bucket={s3['bucket']!r}, "
            f"access_key_id={s3['access_key_id']!r}, secret_access_key={s3['secret_access_key']!r}); "
            "put_url = c.generate_presigned_upload_url('test/key.json', 'application/json'); "
            "req = urllib.request.Request(put_url, data=b'{\"ok\":true}', method='PUT', headers={'Content-Type': 'application/json'}); "
            "urllib.request.urlopen(req, timeout=5).read(); "
            "get_url = c.generate_presigned_url('test/key.json'); "
            "body = urllib.request.urlopen(get_url, timeout=5).read(); "
            "assert body == b'{\"ok\":true}', body"
        )
        proc = subprocess.run(
            [str(API_PYTHON), "-c", probe_code],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        results["s3_object_storage_fixture"] = {
            "returncode": proc.returncode,
            "passed": proc.returncode == 0,
            "fixture": "in-process S3 protocol emulator; does not verify MinIO or R2",
            "output": (proc.stdout + proc.stderr).strip(),
        }

    container_runtime = shutil.which("docker") or shutil.which("podman") or shutil.which("nerdctl")
    results["container_runtime"] = {
        "available": bool(container_runtime),
        "binary": container_runtime,
        "status": "passed" if container_runtime else "unverified",
        "detail": container_runtime or "No local container runtime daemon (docker/podman/nerdctl) installed on host",
    }

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-fixtures", action="store_true", help="Run disposable Postgres/Redis/S3 fixture checks")
    parser.add_argument("--output", type=Path, help="Optional JSON receipt output path")
    args = parser.parse_args()

    git_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, text=True).strip()
    git_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

    report: dict = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "root": git_root,
            "branch": git_branch,
            "head": git_head,
        },
        "inventory": inspect_gate_inventory(),
    }

    if args.verify_fixtures:
        report["fixtures"] = run_disposable_fixture_verification()

    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")

    if args.verify_fixtures:
        fixtures = report["fixtures"]
        for key in ("r04_postgres_completion", "redis_stream_recovery", "s3_object_storage_fixture"):
            if not fixtures[key]["passed"]:
                return 1
        if not fixtures["container_runtime"]["available"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
