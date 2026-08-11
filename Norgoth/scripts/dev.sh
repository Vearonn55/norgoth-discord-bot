#!/usr/bin/env bash
# Norgoth local dev: Redis, Postgres, API, worker, bot, dashboard.
# Usage: ./scripts/dev.sh   (from the Norgoth directory)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing $ROOT/.env — copy .env.example and fill in secrets first."
  exit 1
fi

# ------------------------------------------------------------------
# Detect the LAN address and configure all externally-reachable URLs
# to it, so member verification and other-device access keep working
# across modem/DHCP IP changes without manual .env edits. These exports
# override the static .env values (python-dotenv does not override an
# already-set environment variable, and Next.js reads process.env).
# ------------------------------------------------------------------
echo "==> Detecting LAN address"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [ -z "${LAN_IP:-}" ]; then
  LAN_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [ -z "${LAN_IP:-}" ]; then
  DEF_IF="$(route -n get default 2>/dev/null | awk '/interface: /{print $2}')"
  [ -n "${DEF_IF:-}" ] && LAN_IP="$(ipconfig getifaddr "$DEF_IF" 2>/dev/null || true)"
fi
if [ -z "${LAN_IP:-}" ]; then
  echo "    could not detect a LAN IP; falling back to 127.0.0.1"
  LAN_IP="127.0.0.1"
fi
echo "    LAN address: $LAN_IP"

export NORGOTH_LAN_HOST="$LAN_IP"
export NORGOTH_PUBLIC_API_URL="http://$LAN_IP:8000"
export NORGOTH_DISCORD_REDIRECT_URI="http://$LAN_IP:8000/api/v1/oauth/discord/callback"
export NORGOTH_DISCORD_DASHBOARD_REDIRECT_URI="http://$LAN_IP:8000/api/v1/oauth/discord/dashboard/callback"
export NORGOTH_DASHBOARD_URL="http://$LAN_IP:3000"
export NEXT_PUBLIC_DASHBOARD_URL="http://$LAN_IP:3000"

echo "==> Checking Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  echo "    starting redis-server (daemonized)"
  redis-server --port 6379 --bind 127.0.0.1 --daemonize yes \
    --dir /tmp --logfile /tmp/redis-norgoth.log
fi

echo "==> Checking PostgreSQL"
if ! psql -d norgoth -c 'SELECT 1;' >/dev/null 2>&1; then
  echo "    starting postgresql via brew services"
  brew services start postgresql@14 >/dev/null
  sleep 2
  createdb norgoth 2>/dev/null || true
fi

echo "==> Applying database migrations"
(cd apps/api && .venv/bin/python -m alembic upgrade head)

cleanup() {
  echo "Stopping Norgoth processes..."
  kill 0 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Starting API (http://0.0.0.0:8000 — reachable on the LAN)"
(cd apps/api && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &

echo "==> Starting campaign worker"
(cd apps/api && .venv/bin/python -u -m app.workers.campaign_worker) &

if grep -q '^DISCORD_BOT_TOKEN=.\+' .env; then
  echo "==> Starting Discord bot"
  (cd apps/bot && .venv/bin/python -u main.py) &
else
  echo "==> Skipping bot (DISCORD_BOT_TOKEN not set in .env)"
fi

echo "==> Starting dashboard (http://0.0.0.0:3000 — reachable on the LAN)"
(cd apps/dashboard && npm run dev -- --hostname 0.0.0.0 --port 3000) &

wait
