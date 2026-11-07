import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]


def test_killed_worker_recovery_reaches_terminal_scan_state():
    result = subprocess.run(  # noqa: S603
        ["bash", str(REPO_ROOT / "scripts" / "rehearse_scan_terminal_recovery.sh")],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "terminal_status=completed" in result.stdout
    assert "pending=0" in result.stdout
