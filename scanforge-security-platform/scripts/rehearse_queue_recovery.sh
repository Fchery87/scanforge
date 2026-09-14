#!/usr/bin/env bash
# R12 queue recovery drill: synthetic ScanForge queue messages, a consumer
# killed mid-claim (SIGKILL before ack), then recovery of the orphaned pending
# delivery through the production QueueClient XAUTOCLAIM path. Verifies zero
# message loss and prints claim/recovery latency.
#
# Backend selection (labeled in output):
#   1. local Redis on localhost:6379 if reachable (or R12_REDIS_HOST/PORT),
#   2. else a disposable `redis-server` process on a scratch port if the
#      binary exists (labeled local-redis-disposable),
#   3. else fakeredis (labeled fakeredis-fallback).
# The production client speaks the Upstash REST protocol, so the drill serves
# that protocol from a local shim in front of the chosen Redis backend.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKER_DIR="$REPO_ROOT/apps/worker"
PY="$WORKER_DIR/.venv/bin/python"

log() { printf '[rehearse_queue_recovery] %s\n' "$*"; }

if [ ! -x "$PY" ]; then
  log "no venv at apps/worker/.venv; creating with uv"
  (cd "$WORKER_DIR" && uv venv .venv -p 3.12 && uv pip install -q -p "$PY" -e '.[dev]')
fi
if ! "$PY" -c 'import fakeredis' 2>/dev/null; then
  log "installing fakeredis into the worker venv (fallback backend only)"
  uv pip install -q -p "$PY" fakeredis
fi

export R12_SCRIPTS_DIR="$REPO_ROOT/scripts"
"$PY" "$R12_SCRIPTS_DIR/r12_queue_recovery_drill.py"
