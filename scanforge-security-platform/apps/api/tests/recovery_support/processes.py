"""Process ownership and loopback-only transport for persisted recovery tests."""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx

SUPPORT = Path(__file__).parent
APP = SUPPORT.parents[2]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def isolated_env(root):
    # Do not inherit provider credentials, database URLs, proxies or dotenv files.
    return {"PATH": os.environ["PATH"], "HOME": str(root), "TMPDIR": str(root),
            "APP_ENV": "test", "AI_ENABLED": "false", "SLACK_WEBHOOK_URL": "",
            "PYTHONUNBUFFERED": "1"}


class Processes:
    def __init__(self, root):
        self.root = root
        self.children = []

    def start(self, name, args, env):
        log = (self.root / f"{name}.log").open("w")
        try:
            process = subprocess.Popen(args, cwd=self.root, env=env, stdout=log, stderr=log)
        finally:
            log.close()
        self.children.append(process)
        return process

    def close(self):
        for process in reversed(self.children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def await_http(process, url, *, redis=False):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        assert process.poll() is None, f"service exited: {process.args}"
        try:
            response = httpx.post(url, json=["PING"]) if redis else httpx.get(url)
            if response.status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise AssertionError(f"service not ready: {url}")


def start_redis(processes, worker_python, env):
    binary = shutil.which("redis-server")
    assert binary, "redis-server required"
    port, rest_port = free_port(), free_port()
    processes.start("redis", [binary, "--bind", "127.0.0.1", "--port", str(port),
                             "--dir", str(processes.root), "--save", "", "--appendonly", "no"], env)
    bridge = processes.start("redis-rest", [worker_python, str(SUPPORT / "redis_rest.py"),
                                           str(port), str(rest_port)], env)
    url = f"http://127.0.0.1:{rest_port}"
    await_http(bridge, url, redis=True)
    return url


def redis_command(url, *args):
    response = httpx.post(url, json=args, timeout=10)
    response.raise_for_status()
    payload = response.json()
    assert "error" not in payload, payload
    return payload["result"]
