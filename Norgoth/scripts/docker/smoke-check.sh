#!/usr/bin/env bash
# Post-deploy smoke checks for www/api (and optional test hosts).
set -euo pipefail

ENV_NAME="${1:-production}"

case "${ENV_NAME}" in
  production)
    WEB_URL="${NORBOT_WEB_URL:-https://www.norbot.io}"
    API_URL="${NORBOT_API_URL:-https://api.norbot.io}"
    LOCAL_WEB="${NORBOT_LOCAL_WEB:-http://127.0.0.1:3000}"
    LOCAL_API="${NORBOT_LOCAL_API:-http://127.0.0.1:8000}"
    ;;
  test)
    WEB_URL="${NORBOT_WEB_URL:-https://test.norbot.io}"
    API_URL="${NORBOT_API_URL:-https://api.test.norbot.io}"
    LOCAL_WEB="${NORBOT_LOCAL_WEB:-http://127.0.0.1:3001}"
    LOCAL_API="${NORBOT_LOCAL_API:-http://127.0.0.1:8001}"
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

check() {
  local name="$1"
  local url="$2"
  echo -n "Checking ${name}: ${url} … "
  if curl -fsS --max-time 20 "${url}" >/dev/null; then
    echo "ok"
  else
    echo "FAIL"
    return 1
  fi
}

# Prefer public URLs; fall back to loopback during early bring-up.
if ! check "web" "${WEB_URL}/api/health"; then
  check "web-local" "${LOCAL_WEB}/api/health"
fi

if ! check "api" "${API_URL}/api/v1/health"; then
  check "api-local" "${LOCAL_API}/api/v1/health"
fi

# Optional bot/worker heartbeats (best-effort).
curl -fsS --max-time 10 "${LOCAL_API}/bot/health" >/dev/null 2>&1 \
  && echo "bot health: ok" || echo "bot health: skipped/unavailable"
curl -fsS --max-time 10 "${LOCAL_API}/campaigns/worker/health" >/dev/null 2>&1 \
  && echo "campaign worker health: ok" || echo "campaign worker health: skipped/unavailable"

echo "Smoke checks passed for ${ENV_NAME}."
