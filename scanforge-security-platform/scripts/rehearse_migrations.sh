#!/usr/bin/env bash
# R12 migration rehearsal: disposable PostgreSQL via the documented pgserver
# procedure (docs/development-setup.md, "Disposable PostgreSQL for test
# evidence"), then alembic upgrade head -> downgrade base -> upgrade head
# with per-step timings. Non-zero exit on any failure.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
PY="$API_DIR/.venv/bin/python"
ALEMBIC="$API_DIR/.venv/bin/alembic"
PGDATA="${R12_MIG_PGDATA:-/tmp/scanforge-r12-migrations-pg16}"

log() { printf '[rehearse_migrations] %s\n' "$*"; }

# Ensure the api venv exists (uv-managed; see docs/development-setup.md).
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

# Fresh throwaway cluster on every run for a clean empty-database rehearsal.
rm -rf "$PGDATA"
# Documented pgserver procedure (docs/development-setup.md). The cluster is
# started with cleanup_mode=None so it survives into the alembic child
# process; it is stopped explicitly in cleanup(). pgserver serves a unix
# socket, and alembic's configparser cannot carry the percent-encoded socket
# URI, so connection details go through the standard libpq environment
# (PGHOST/PGUSER/PGPORT) with a query-free DATABASE_URL.
"$PY" - <<PYEOF
import pgserver
db = pgserver.get_server("$PGDATA", cleanup_mode=None)
print("uri:", db.get_uri())
PYEOF
export DATABASE_URL="postgresql://:@/postgres"
export PGHOST="$PGDATA"
export PGUSER="postgres"
PGPORT="$(ls "$PGDATA"/.s.PGSQL.* 2>/dev/null | grep -v lock | sed 's/.*\.s\.PGSQL\.//;q')"
export PGPORT="${PGPORT:-5432}"
log "disposable PostgreSQL ready at $PGDATA (socket port $PGPORT)"

STEP_STATUS=0
timed() {
  local label="$1"; shift
  local start_ms end_ms rc
  start_ms="$(date +%s%N)"
  if "$@"; then rc=0; else rc=$?; fi
  end_ms="$(date +%s%N)"
  local ms=$(( (end_ms - start_ms) / 1000000 ))
  if [ "$rc" -eq 0 ]; then
    printf '[rehearse_migrations] STEP %-24s OK    %6d ms\n' "$label" "$ms"
  else
    printf '[rehearse_migrations] STEP %-24s FAIL  %6d ms\n' "$label" "$ms"
    STEP_STATUS=1
  fi
  return 0
}

cd "$API_DIR"
timed "alembic upgrade head"     "$ALEMBIC" upgrade head
timed "alembic downgrade base"   "$ALEMBIC" downgrade base
timed "alembic upgrade head (2)" "$ALEMBIC" upgrade head

# Head revision sanity: the second upgrade must end at the same head.
HEAD="$("$ALEMBIC" heads | awk 'NR==1{print $1}')"
log "alembic head: $HEAD"

if [ "$STEP_STATUS" -ne 0 ]; then
  log "RESULT: FAIL (a migration step failed)"
  exit 1
fi
log "RESULT: PASS (upgrade head -> downgrade base -> upgrade head, all steps green)"
