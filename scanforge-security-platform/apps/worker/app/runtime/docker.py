from __future__ import annotations

import os
import re
import selectors
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.runtime.models import ScanRuntimeRequest, ScanRuntimeResult

_WRAPPER = """
mkdir -p /tmp/.runtime
ulimit -f "$1"
shift
"$@" >/tmp/.runtime/stdout 2>/tmp/.runtime/stderr
printf '%s' "$?" >/tmp/.runtime/exit
tar -c -C /tmp .runtime -C /workspace --transform='s,^output,artifacts,' output
"""


@dataclass
class _Execution:
    source: Path
    name: str
    canceled: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)
    cleanup_error: Exception | None = None


class DockerScanRuntime:
    def __init__(self, image: str, docker_binary: str = "docker") -> None:
        if not image or not re.fullmatch(r".+@sha256:[0-9a-fA-F]{64}", image):
            raise ValueError("scanner image must be pinned by digest")
        if not shutil.which(docker_binary):
            raise RuntimeError("Docker is required for the private-beta scanner runtime")
        self.image = image
        self.docker_binary = docker_binary
        self._lock = threading.Lock()
        self._active: dict[str, _Execution] = {}
        self._canceled_sources: set[Path] = set()

    def build_command(self, request: ScanRuntimeRequest, container_name: str | None = None) -> list[str]:
        if request.network_enabled:
            raise ValueError("scanner runtime network access is disabled")
        if (
            min(
                request.timeout_seconds,
                request.disk_limit_mb,
                request.output_limit_bytes,
                request.memory_limit_mb,
                request.process_limit,
                request.cpu_limit,
            )
            <= 0
        ):
            raise ValueError("scanner runtime limits must be positive")
        source = request.source_directory.resolve(strict=True)
        if not source.is_dir() or "," in str(source):
            raise ValueError("invalid scanner source directory")
        return [
            self.docker_binary,
            "run",
            "--name",
            container_name or f"scanforge-{uuid4().hex}",
            "--user",
            "65532:65532",
            "--read-only",
            "--network=none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--pids-limit",
            str(request.process_limit),
            "--memory",
            f"{request.memory_limit_mb}m",
            "--cpus",
            str(request.cpu_limit),
            "--log-driver",
            "none",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={request.disk_limit_mb}m,uid=65532,gid=65532",  # noqa: S108
            "--tmpfs",
            f"/workspace/output:rw,noexec,nosuid,nodev,size={request.disk_limit_mb}m,uid=65532,gid=65532",
            "--mount",
            f"type=bind,src={source},dst=/workspace/source,readonly",
            "--workdir",
            "/workspace/source",
            "--entrypoint",
            "/bin/sh",
            self.image,
            "-c",
            _WRAPPER,
            "scanner",
            str(max(1, request.output_limit_bytes // 512)),
            request.executable,
            *request.arguments,
        ]

    def cancel(self, source_directory: Path) -> None:
        source = source_directory.resolve()
        with self._lock:
            self._canceled_sources.add(source)
            executions = [item for item in self._active.values() if item.source == source]
            for execution in executions:
                execution.canceled.set()
        for execution in executions:
            if not execution.finished.wait(timeout=20):
                raise RuntimeError(f"Scanner cleanup did not finish for {execution.name}")
            if execution.cleanup_error is not None:
                raise RuntimeError(f"Scanner cleanup failed for {execution.name}") from execution.cleanup_error

    def _remove_container(self, name: str) -> None:
        result = subprocess.run(
            [self.docker_binary, "rm", "-f", name],
            capture_output=True,
            timeout=10,
            env={"PATH": "/usr/bin:/bin"},
        )
        if result.returncode and b"No such container" not in result.stderr:
            raise RuntimeError(f"Scanner container cleanup failed for {name}")

    def run(self, request: ScanRuntimeRequest) -> ScanRuntimeResult:
        started = time.monotonic()
        execution = _Execution(request.source_directory.resolve(), f"scanforge-{uuid4().hex}")
        with self._lock:
            if execution.source in self._canceled_sources:
                return ScanRuntimeResult(130, "", "Scanner canceled",
                                         int((time.monotonic() - started) * 1000))
            self._active[execution.name] = execution
        process = None
        try:
            command = self.build_command(request, execution.name)
            with self._lock:
                if execution.canceled.is_set():
                    return ScanRuntimeResult(130, "", "Scanner canceled",
                                             int((time.monotonic() - started) * 1000))
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={"PATH": "/usr/bin:/bin"}
                )
            with tempfile.TemporaryFile() as spool:
                timed_out, canceled, stderr = self._collect(process, spool, request, execution, started)
                if timed_out or canceled:
                    return ScanRuntimeResult(
                        124 if timed_out else 130,
                        "",
                        "Scanner timed out" if timed_out else "Scanner canceled",
                        int((time.monotonic() - started) * 1000),
                        timed_out=timed_out,
                    )
                if process.returncode:
                    return ScanRuntimeResult(process.returncode, "", stderr, int((time.monotonic() - started) * 1000))
                spool.seek(0)
                return self._read_export(spool, request, int((time.monotonic() - started) * 1000))
        finally:
            try:
                if process is not None:
                    self._remove_container(execution.name)
            except Exception as exc:
                execution.cleanup_error = exc
                raise
            finally:
                try:
                    if process is not None:
                        if process.poll() is None:
                            process.kill()
                        process.wait(timeout=5)
                        if process.stdout:
                            process.stdout.close()
                        if process.stderr:
                            process.stderr.close()
                except Exception as exc:
                    execution.cleanup_error = exc
                    raise
                finally:
                    with self._lock:
                        self._active.pop(execution.name, None)
                    execution.finished.set()

    def _collect(self, process, spool, request, execution, started):
        size = 0
        stderr = bytearray()
        stream_limit = request.output_limit_bytes + 1024 * 1024
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "archive")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                timed_out = time.monotonic() - started > request.timeout_seconds
                if timed_out or execution.canceled.is_set():
                    return timed_out, execution.canceled.is_set(), ""
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif key.data == "archive":
                        size += len(chunk)
                        if size > stream_limit:
                            raise RuntimeError("Scanner export exceeds output limit")
                        spool.write(chunk)
                    else:
                        remaining = request.output_limit_bytes - len(stderr)
                        stderr.extend(chunk[: max(0, remaining)])
        process.wait(timeout=max(0.1, request.timeout_seconds - (time.monotonic() - started)))
        return False, False, stderr.decode(errors="replace")

    def _read_export(self, spool, request: ScanRuntimeRequest, duration_ms: int) -> ScanRuntimeResult:
        try:
            with tarfile.open(fileobj=spool, mode="r:") as archive:
                members = []
                total = 0
                names = set()
                for member in archive:
                    path = PurePosixPath(member.name)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or not path.parts
                        or path.parts[0] not in {"artifacts", ".runtime"}
                        or not (member.isdir() or member.isfile())
                        or member.name in names
                    ):
                        raise RuntimeError("Scanner export contains unsafe member")
                    if member.size < 0:
                        raise RuntimeError("Scanner export contains unsafe size")
                    total += member.size
                    if total > request.output_limit_bytes or len(members) >= 4096:
                        raise RuntimeError("Scanner export exceeds output limit")
                    names.add(member.name)
                    members.append(member)
                metadata = {}
                output = request.output_directory.resolve(strict=True)
                for member in members:
                    path = PurePosixPath(member.name)
                    if member.isdir():
                        continue
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise RuntimeError("Scanner export is incomplete")
                    with stream:
                        if path.parts[0] == ".runtime":
                            if member.name not in {".runtime/exit", ".runtime/stdout", ".runtime/stderr"}:
                                raise RuntimeError("Scanner export contains unsafe metadata")
                            metadata[path.name] = stream.read().decode(errors="replace")
                        else:
                            target = output.joinpath(*path.parts[1:])
                            if not target.resolve().is_relative_to(output) or target.is_symlink():
                                raise RuntimeError("Scanner export contains unsafe destination")
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with target.open("xb") as destination:
                                shutil.copyfileobj(stream, destination, length=65536)
                if set(metadata) != {"exit", "stdout", "stderr"} or not metadata["exit"].strip().isdigit():
                    raise RuntimeError("Scanner export is missing execution status")
                return ScanRuntimeResult(int(metadata["exit"]), metadata["stdout"], metadata["stderr"], duration_ms)
        except (tarfile.TarError, OSError) as exc:
            raise RuntimeError("Scanner export is invalid") from exc
