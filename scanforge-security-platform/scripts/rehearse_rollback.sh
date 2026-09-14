#!/usr/bin/env bash
# R12 rollback drill: exercises the documented completion rollback / receipt
# semantics (spec/2026-09-13-scan-evidence-decisions.md D6; readiness plan R04)
# through the service layer:
#   1. first completion writes exactly one server-owned receipt,
#   2. identical replay returns the STORED receipt (no second receipt row),
#   3. conflicting replay of the same completion identity raises
#      CompletionPayloadConflict (conflict family surfaced as HTTP 409),
#   4. stale-identity replay raises CompletionSuperseded (HTTP 409).
# Runs against SQLite always and against a disposable PostgreSQL (pgserver,
# docs/development-setup.md) when available. Non-zero exit on any failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
PY="$API_DIR/.venv/bin/python"
PGDATA="${R12_RB_PGDATA:-/tmp/scanforge-r12-rollback-pg16}"

log() { printf '[rehearse_rollback] %s\n' "$*"; }

if [ ! -x "$PY" ]; then
  log "no venv at apps/api/.venv; creating with uv"
  (cd "$API_DIR" && uv venv .venv -p 3.12 && uv pip install -q -p "$PY" -e '.[dev]')
fi
if ! "$PY" -c 'import pgserver' 2>/dev/null; then
  log "installing pgserver into the api venv (documented disposable-PG tool)"
  uv pip install -q -p "$PY" pgserver
fi

cleanup() {
  "$PY" - <<PYEOF >/dev/null 2>&1 || true
import pgserver
try:
    pgserver.get_server("$PGDATA", cleanup_mode=None).cleanup()
except Exception:
    pass
PYEOF
  if [ "${R12_KEEP_PGDATA:-0}" != "1" ]; then
    rm -rf "$PGDATA"
  fi
}
trap cleanup EXIT

rm -rf "$PGDATA"
# Settings requires DATABASE_URL at import time; the drill drives its own
# engines, so a placeholder is enough for the SQLite phase.
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///:memory:}"

export R12_SCRIPTS_DIR="$REPO_ROOT/scripts"

log "phase 1: SQLite backend"
"$PY" - <<'DRILLEOF'
import asyncio, os, sys
sys.path.insert(0, os.environ["R12_SCRIPTS_DIR"])
from r12_rollback_drill import run_drill
sys.exit(asyncio.run(run_drill("sqlite")))
DRILLEOF

log "phase 2: disposable PostgreSQL backend (pgserver)"
export R12_PG_URI="$("$PY" - <<PYEOF
import pgserver
# cleanup_mode=None: keep the cluster alive across processes; stopped in cleanup()
print(pgserver.get_server("$PGDATA", cleanup_mode=None).get_uri())
PYEOF
)"
log "disposable PostgreSQL ready at $PGDATA"
"$PY" - <<'DRILLEOF'
import asyncio, os, sys
sys.path.insert(0, os.environ["R12_SCRIPTS_DIR"])
from r12_rollback_drill import run_drill
sys.exit(asyncio.run(run_drill("postgres", pg_uri=os.environ["R12_PG_URI"])))
DRILLEOF

log "RESULT: PASS (receipt replay + conflict 409 semantics on SQLite and disposable PG)"
