#!/usr/bin/env bash
# Turnkey production deploy for DSCI-DecentBio.
#
#   backend  -> Railway   (apps/desci-platform/backend, Dockerfile)
#   frontend -> Vercel    (apps/desci-platform/frontend, dist)
#
# This script does NOT contain any secrets. It runs the env preflight, then
# drives the Railway/Vercel CLIs (which read their own auth from your login or
# the RAILWAY_TOKEN / VERCEL_TOKEN env vars). Configure the runtime env first
# (see `python scripts/env_doctor.py`).
#
# Usage:
#   scripts/deploy.sh            # preflight + deploy both
#   scripts/deploy.sh --dry-run  # print what would run, change nothing
#   scripts/deploy.sh backend    # deploy only the backend
#   scripts/deploy.sh frontend   # deploy only the frontend
set -euo pipefail

DESCI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
TARGET="all"

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    backend|frontend|all) TARGET="$arg" ;;
    -h|--help) sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy] WARN:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[deploy] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if [[ "$DRY_RUN" == 1 ]]; then
    printf '\033[2m  would run: %s\033[0m\n' "$*"
  else
    log "running: $*"
    "$@"
  fi
}

require_cli() {
  command -v "$1" >/dev/null 2>&1 && return 0
  if [[ "$DRY_RUN" == 1 ]]; then
    warn "'$1' CLI not found (install: $2). Required for a real deploy; continuing dry-run."
    return 0
  fi
  die "'$1' CLI not found. Install it ($2) and authenticate before deploying."
}

preflight() {
  log "env preflight (env_doctor)"
  if command -v python >/dev/null 2>&1; then
    python "$DESCI_ROOT/scripts/env_doctor.py" || warn "env_doctor reported issues — review the WARN/FAIL items above before going live."
  else
    warn "python not found; skipping env_doctor preflight."
  fi
}

deploy_backend() {
  log "backend -> Railway"
  require_cli railway "npm i -g @railway/cli"
  ( cd "$DESCI_ROOT/backend" && run railway up --detach )
}

deploy_frontend() {
  log "frontend -> Vercel"
  require_cli vercel "npm i -g vercel"
  ( cd "$DESCI_ROOT/frontend" && run vercel deploy --prod )
}

preflight
case "$TARGET" in
  backend)  deploy_backend ;;
  frontend) deploy_frontend ;;
  all)      deploy_backend; deploy_frontend ;;
esac
log "done (dry-run=$DRY_RUN, target=$TARGET)."
