#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER_DIR="$REPO_ROOT/apps/worker"
PY="$WORKER_DIR/.venv/bin/python"

if [ ! -x "$PY" ]; then
  printf '[rehearse_scan_terminal_recovery] missing worker venv: %s\n' "$PY" >&2
  exit 1
fi

PYTHONPATH="$WORKER_DIR" "$PY" "$REPO_ROOT/scripts/rehearse_scan_terminal_recovery.py"
