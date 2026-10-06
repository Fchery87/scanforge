import io
import tarfile
from unittest.mock import patch

import pytest

from app.runtime.docker import DockerScanRuntime
from app.runtime.models import ScanRuntimeRequest


def runtime():
    with patch("app.runtime.docker.shutil.which", return_value="/usr/bin/docker"):
        return DockerScanRuntime("scanner@sha256:" + "a" * 64)


def archive(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        for name, content in entries:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            stream.addfile(member, io.BytesIO(content))
    buffer.seek(0)
    return buffer


def request(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    return ScanRuntimeRequest("scanner", (), source, output, output_limit_bytes=256)


def test_export_preserves_report_and_scanner_stdout(tmp_path):
    data = archive(
        [
            (".runtime/exit", b"1"),
            (".runtime/stdout", b'{"checks":[]}'),
            (".runtime/stderr", b""),
            ("artifacts/report.json", b'{"findings":[]}'),
        ]
    )
    result = runtime()._read_export(data, request(tmp_path), 10)
    assert result.exit_code == 1
    assert result.stdout == '{"checks":[]}'
    assert (tmp_path / "output/report.json").read_text() == '{"findings":[]}'


@pytest.mark.parametrize("name", ["artifacts/../escape", "/escape", "artifacts/a/../../escape"])
def test_export_rejects_path_escape(tmp_path, name):
    with pytest.raises(RuntimeError, match="unsafe"):
        runtime()._read_export(archive([(name, b"x")]), request(tmp_path), 10)
    assert not (tmp_path / "escape").exists()


def test_export_rejects_symlink(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        member = tarfile.TarInfo("artifacts/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc/passwd"
        stream.addfile(member)
    buffer.seek(0)
    with pytest.raises(RuntimeError, match="unsafe"):
        runtime()._read_export(buffer, request(tmp_path), 10)


def test_export_bounds_cumulative_payload(tmp_path):
    data = archive([("artifacts/a", b"x" * 150), ("artifacts/b", b"x" * 150)])
    with pytest.raises(RuntimeError, match="limit"):
        runtime()._read_export(data, request(tmp_path), 10)
    assert list((tmp_path / "output").iterdir()) == []


def test_run_removes_named_container_after_invalid_export(tmp_path):
    import subprocess
    import sys

    original_popen = subprocess.Popen
    recorded = []

    def popen(command, **kwargs):
        recorded.append(command)
        return original_popen([sys.executable, "-c", 'import sys; sys.stdout.write("invalid archive")'], **kwargs)

    worker = runtime()
    with (
        patch("app.runtime.docker.subprocess.Popen", side_effect=popen),
        patch.object(worker, "_remove_container") as remove,
    ):
        with pytest.raises(RuntimeError, match="invalid"):
            worker.run(request(tmp_path))
    name = recorded[0][recorded[0].index("--name") + 1]
    remove.assert_called_once_with(name)
    assert worker._active == {}


def test_timeout_terminates_container_and_client(tmp_path):
    import subprocess
    import sys
    from dataclasses import replace

    original_popen = subprocess.Popen
    clients = []

    def popen(command, **kwargs):
        client = original_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        clients.append(client)
        return client

    worker = runtime()
    with (
        patch("app.runtime.docker.subprocess.Popen", side_effect=popen),
        patch.object(worker, "_remove_container") as remove,
    ):
        result = worker.run(replace(request(tmp_path), timeout_seconds=0.1))
    assert result.exit_code == 124
    assert result.timed_out is True
    assert clients[0].poll() is not None
    remove.assert_called_once()


def test_stream_limit_is_enforced_while_process_runs(tmp_path):
    import subprocess
    import sys

    original_popen = subprocess.Popen

    def popen(command, **kwargs):
        return original_popen(
            [sys.executable, "-c", 'import sys; sys.stdout.buffer.write(b"x" * 2000000); sys.stdout.flush()'], **kwargs
        )

    worker = runtime()
    with (
        patch("app.runtime.docker.subprocess.Popen", side_effect=popen),
        patch.object(worker, "_remove_container") as remove,
    ):
        with pytest.raises(RuntimeError, match="limit"):
            worker.run(request(tmp_path))
    remove.assert_called_once()


def test_cancel_waits_for_named_container_cleanup(tmp_path):
    import subprocess
    import sys
    import threading

    original_popen = subprocess.Popen
    ready = threading.Event()

    def popen(command, **kwargs):
        client = original_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        ready.set()
        return client

    worker = runtime()
    scan_request = request(tmp_path)
    results = []
    with (
        patch("app.runtime.docker.subprocess.Popen", side_effect=popen),
        patch.object(worker, "_remove_container") as remove,
    ):
        thread = threading.Thread(target=lambda: results.append(worker.run(scan_request)))
        thread.start()
        assert ready.wait(2)
        worker.cancel(scan_request.source_directory)
        thread.join(2)
    assert not thread.is_alive()
    assert results[0].exit_code == 130
    assert worker._active == {}
    remove.assert_called_once()


def test_cleanup_daemon_failure_is_observable(tmp_path):
    import subprocess

    worker = runtime()
    completed = subprocess.CompletedProcess([], 1, b"", b"daemon unavailable")
    with patch("app.runtime.docker.subprocess.run", return_value=completed):
        with pytest.raises(RuntimeError, match="cleanup failed"):
            worker._remove_container("scanforge-test")


@pytest.mark.parametrize("member_type", [tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE])
def test_export_rejects_links_devices_and_pipes(tmp_path, member_type):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as stream:
        member = tarfile.TarInfo("artifacts/hostile")
        member.type = member_type
        member.linkname = "artifacts/other"
        stream.addfile(member)
    buffer.seek(0)
    with pytest.raises(RuntimeError, match="unsafe"):
        runtime()._read_export(buffer, request(tmp_path), 10)


def test_export_rejects_existing_output_symlink(tmp_path):
    scan_request = request(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (scan_request.output_directory / "link").symlink_to(outside)
    data = archive([("artifacts/link/report.json", b"{}")])
    with pytest.raises(RuntimeError, match="unsafe"):
        runtime()._read_export(data, scan_request, 10)
    assert list(outside.iterdir()) == []


def test_wrapper_exports_real_command_exit_stdout_and_artifacts(tmp_path):
    import subprocess
    import sys

    from app.runtime.docker import _WRAPPER

    scan_request = request(tmp_path)
    workspace = tmp_path / "container"
    output = workspace / "output"
    output.mkdir(parents=True)
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    wrapper = _WRAPPER.replace("/tmp", str(metadata)).replace("/workspace", str(workspace))  # noqa: S108
    script = 'from pathlib import Path; import sys; Path(sys.argv[1]).write_text("{}"); print("hello"); sys.exit(17)'
    completed = subprocess.run(  # noqa: S603
        ["/bin/sh", "-c", wrapper, "scanner", "64", sys.executable, "-c", script, str(output / "report.json")],
        capture_output=True,
        check=True,
    )
    result = runtime()._read_export(io.BytesIO(completed.stdout), scan_request, 10)
    assert result.exit_code == 17
    assert result.stdout == "hello\n"
    assert (scan_request.output_directory / "report.json").read_text() == "{}"


def test_cancel_during_command_build_prevents_container_launch(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    worker = runtime()
    scan_request = request(tmp_path)
    building = threading.Event()
    release = threading.Event()

    def build_command(_request, name):
        building.set()
        assert release.wait(timeout=5)
        return ["docker", "run", "--name", name]

    with (
        patch.object(worker, "build_command", side_effect=build_command),
        patch("app.runtime.docker.subprocess.Popen") as launch,
        patch.object(worker, "_remove_container") as remove,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        execution = executor.submit(worker.run, scan_request)
        assert building.wait(timeout=5)
        with worker._lock:
            active = list(worker._active.values())
        assert len(active) == 1
        cancellation = executor.submit(worker.cancel, scan_request.source_directory)
        try:
            assert active[0].canceled.wait(timeout=5)
        finally:
            release.set()
        result = execution.result(timeout=5)
        cancellation.result(timeout=5)
    assert result.exit_code == 130
    launch.assert_not_called()
    remove.assert_not_called()
    assert worker._active == {}


@pytest.mark.parametrize("remove_source", [False, True])
def test_cancel_before_queued_runtime_call_prevents_container_launch(tmp_path, remove_source):
    import shutil
    import threading
    from concurrent.futures import ThreadPoolExecutor

    worker = runtime()
    scan_request = request(tmp_path)
    blocked = threading.Event()
    release = threading.Event()

    def occupy_executor():
        blocked.set()
        assert release.wait(timeout=5)

    with (
        ThreadPoolExecutor(max_workers=1) as executor,
        patch("app.runtime.docker.subprocess.Popen") as launch,
        patch.object(worker, "_remove_container") as remove,
    ):
        blocker = executor.submit(occupy_executor)
        assert blocked.wait(timeout=5)
        delayed = executor.submit(worker.run, scan_request)
        try:
            worker.cancel(scan_request.source_directory)
            assert worker._active == {}
            if remove_source:
                shutil.rmtree(scan_request.source_directory)
        finally:
            release.set()
        blocker.result(timeout=5)
        result = delayed.result(timeout=5)
        repeated = worker.run(scan_request)
    assert result.exit_code == 130
    assert repeated.exit_code == 130
    launch.assert_not_called()
    remove.assert_not_called()
    assert worker._active == {}
