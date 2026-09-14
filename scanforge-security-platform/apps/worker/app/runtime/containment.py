"""Process-group containment for scanner subprocesses.

A timeout must kill the whole scanner process tree, not only the direct
child. Scanners are therefore started as their own POSIX session/process
group, and a deadline expiry SIGKILLs the entire group so spawned
grandchildren cannot outlive the kill.
"""
from __future__ import annotations

import os
import signal
import subprocess

POSIX = os.name == "posix"


def popen_scanner_process(command: list[str], **kwargs: object) -> subprocess.Popen:
    """Start a scanner as the leader of its own process group on POSIX."""
    if POSIX:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)  # noqa: S603


def kill_process_tree(process: subprocess.Popen) -> None:
    """SIGKILL the scanner's whole process group, then the direct child."""
    if POSIX:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.kill()
