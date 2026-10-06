import json
import os
import shutil
import subprocess

import pytest

from app.runtime.docker import DockerScanRuntime
from app.runtime.models import ScanRuntimeRequest

pytestmark = pytest.mark.skipif(os.environ.get("SCANFORGE_LIVE_DOCKER") != "1", reason="Live Docker gate is opt-in")


@pytest.fixture
def contained(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    source.chmod(0o755)
    output = tmp_path / "output"
    output.mkdir()
    runtime = DockerScanRuntime(os.environ["SCANNER_IMAGE"])
    return runtime, source, output


def execute(contained, code, *, timeout=10):
    runtime, source, output = contained
    return runtime.run(ScanRuntimeRequest(
        executable="python3", arguments=("-c", code), source_directory=source,
        output_directory=output, timeout_seconds=timeout, disk_limit_mb=16,
        memory_limit_mb=128, output_limit_bytes=1024 * 1024,
    ))


def test_live_container_is_nonroot_readonly_and_credential_free(contained):
    _, source, _ = contained
    (source / "input.txt").write_text("fixture")
    (source / "input.txt").chmod(0o644)
    result = execute(contained, '''
import json, os, socket
try:
    open('/workspace/source/input.txt', 'w')
    readonly = False
except OSError:
    readonly = True
try:
    socket.create_connection(('1.1.1.1', 443), timeout=1)
    isolated = False
except OSError:
    isolated = True
keys = [key for key in os.environ if any(word in key for word in ('TOKEN', 'CREDENTIAL', 'SECRET', 'DATABASE_URL'))]
print(json.dumps({'uid': os.getuid(), 'readonly': readonly, 'isolated': isolated, 'keys': keys}))
''')
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"uid": 65532, "readonly": True, "isolated": True, "keys": []}
    assert (source / "input.txt").read_text() == "fixture"


def containers():
    result = subprocess.run(
        [shutil.which("docker") or "/usr/bin/docker", "ps", "-aq", "--filter", "name=scanforge-"],
        capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


def test_live_timeout_leaves_no_container_after_repeated_runs(contained):
    before = containers()
    for _ in range(10):
        result = execute(contained, "import time; time.sleep(60)", timeout=1)
        assert result.timed_out
        assert containers() == before


def test_live_output_symlink_is_rejected_and_cleaned(contained):
    before = containers()
    with pytest.raises(RuntimeError, match="unsafe"):
        execute(contained, "import os; os.symlink('/etc/passwd', '/workspace/output/escape')")
    assert containers() == before


def test_live_excess_output_fails_without_host_disk_growth(contained):
    _, _, output = contained
    before = containers()
    try:
        result = execute(contained, "open('/workspace/output/large', 'wb').write(b'x' * (32 * 1024 * 1024))")
        assert result.exit_code != 0
    except RuntimeError as exc:
        assert "limit" in str(exc).lower() or "size" in str(exc).lower()
    assert containers() == before
    assert sum(path.stat().st_size for path in output.rglob('*') if path.is_file()) <= 1024 * 1024
