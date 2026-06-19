#!/usr/bin/env bash
# Push backend environment variables to a Railway service in one shot.
#
# After `railway login` + `railway link`, deploying still means setting ~12
# backend variables by hand in the Railway dashboard — tedious and easy to get
# wrong. This reads a local env file (KEY=value lines) and applies every entry
# with `railway variable set`, so the deploy is genuinely one step:
#
#   railway login && railway link        # one-time, interactive (browser)
#   cp .env.example .env.production       # then fill in real values
#   scripts/set_railway_env.sh .env.production
#   scripts/deploy.sh backend
#
# This script contains NO secrets. The env file you point it at does — keep it
# out of git (.env* is already ignored) and never commit it.
#
# Usage:
#   scripts/set_railway_env.sh [ENV_FILE] [--service NAME] [--dry-run]
#
# Defaults: ENV_FILE=.env.production, --service biolinker
set -euo pipefail

ENV_FILE=".env.production"
SERVICE="biolinker"
DRY_RUN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --service) SERVICE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) ENV_FILE="$1"; shift ;;
  esac
done

log() { printf '\033[1;36m[railway-env]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[railway-env] WARN:\033[0m %s\n' "$*" >&2; }

if [ ! -f "$ENV_FILE" ]; then
  echo "env file not found: $ENV_FILE" >&2
  echo "Create it (e.g. 'cp .env.example $ENV_FILE') and fill in real values first." >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 0 ] && ! command -v railway >/dev/null 2>&1; then
  echo "railway CLI not found. Install with: npm i -g @railway/cli" >&2
  exit 1
fi

# Required keys for a functional production backend (see docs/GO_LIVE.md).
# Missing ones are warned about, not fatal — optional features can come later.
REQUIRED="DATABASE_URL ALLOWED_ORIGINS DESCI_FRONTEND_URL"
RECOMMENDED="FIREBASE_SERVICE_ACCOUNT_JSON SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY REDIS_URL"

count=0
declare -a present=()
# Read KEY=value lines, skipping blanks, comments, and `export ` prefixes.
while IFS= read -r line || [ -n "$line" ]; do
  line="${line#export }"
  case "$line" in
    ''|\#*) continue ;;
    *=*) : ;;
    *) continue ;;
  esac
  key="${line%%=*}"
  # trim surrounding whitespace from the key
  key="$(printf '%s' "$key" | tr -d '[:space:]')"
  [ -z "$key" ] && continue
  present+=("$key")
  if [ "$DRY_RUN" -eq 1 ]; then
    log "would set $key (service=$SERVICE)"
  else
    # Pass the whole KEY=value pair; --skip-deploys avoids a redeploy per var.
    railway variable set "$line" --service "$SERVICE" --skip-deploys >/dev/null
    log "set $key"
  fi
  count=$((count + 1))
done < "$ENV_FILE"

# Warn about required/recommended keys that the env file did not provide.
for k in $REQUIRED; do
  case " ${present[*]} " in *" $k "*) : ;; *) warn "required key missing from $ENV_FILE: $k" ;; esac
done
for k in $RECOMMENDED; do
  case " ${present[*]} " in *" $k "*) : ;; *) warn "recommended key missing: $k" ;; esac
done

log "done — $count variable(s) processed (dry-run=$DRY_RUN, service=$SERVICE)."
[ "$DRY_RUN" -eq 0 ] && log "next: scripts/deploy.sh backend"
