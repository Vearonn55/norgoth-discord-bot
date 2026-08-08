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

echo "==> Starting API (http://127.0.0.1:8000)"
(cd apps/api && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &

echo "==> Starting campaign worker"
(cd apps/api && .venv/bin/python -u -m app.workers.campaign_worker) &

if grep -q '^DISCORD_BOT_TOKEN=.\+' .env; then
  echo "==> Starting Discord bot"
  (cd apps/bot && .venv/bin/python -u main.py) &
else
  echo "==> Skipping bot (DISCORD_BOT_TOKEN not set in .env)"
fi

echo "==> Starting dashboard (http://127.0.0.1:3000)"
(cd apps/dashboard && npm run dev -- --port 3000) &

wait
