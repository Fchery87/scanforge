#!/usr/bin/env bash
# Provision or verify a dedicated per-organization ScanForge Linux worker host (ADR-011).
# Does NOT purchase or provision cloud VMs automatically; configures or verifies the local host.
set -euo pipefail

MODE="provision"
WORKSPACE_ROOT="${WORKER_WORKSPACE_ROOT:-/var/lib/scanforge/workspaces}"
ENV_FILE="${WORKER_ENV_FILE:-/etc/scanforge/worker.env}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify-only)
      MODE="verify"
      shift
      ;;
    --workspace-root)
      WORKSPACE_ROOT="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

command -v git >/dev/null 2>&1 || { echo "ERROR: git binary is required on the worker host" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker binary is required on the worker host" >&2; exit 1; }

if [[ "$MODE" == "verify" ]]; then
  mkdir -p "$WORKSPACE_ROOT"
  chmod 0700 "$WORKSPACE_ROOT"
  echo "Verified git=$(command -v git), docker=$(command -v docker), workspace_root=$WORKSPACE_ROOT"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: full host provisioning requires root (or use --verify-only)" >&2
  exit 1
fi

if ! id -u scanforge-worker >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/scanforge --shell /usr/sbin/nologin scanforge-worker
fi
usermod -aG docker scanforge-worker

install -d -m 0700 -o scanforge-worker -g scanforge-worker "$WORKSPACE_ROOT"
install -d -m 0750 -o root -g scanforge-worker "$(dirname "$ENV_FILE")"

if [[ -f "$ENV_FILE" ]]; then
  # Verify forbidden API-only secrets are never present on a worker host
  for forbidden in DATABASE_URL R2_SECRET_ACCESS_KEY R2_ACCESS_KEY_ID WORKER_CREDENTIAL_PEPPER SCHEDULER_API_KEY; do
    if grep -Eq "^${forbidden}=" "$ENV_FILE"; then
      echo "ERROR: forbidden API secret ${forbidden} found in ${ENV_FILE}" >&2
      exit 1
    fi
  done
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
install -m 0644 "$REPO_ROOT/infra/worker/scanforge-worker.service" /etc/systemd/system/scanforge-worker.service
systemctl daemon-reload
echo "Provisioned scanforge-worker.service with workspace root $WORKSPACE_ROOT"
