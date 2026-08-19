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

url_host() {
  python3 -c 'from urllib.parse import urlparse; import sys; print(urlparse(sys.argv[1]).hostname or "")' "$1"
}

host_resolves() {
  local host="$1"
  [[ -n "${host}" ]] || return 1
  getent ahostsv4 "${host}" >/dev/null 2>&1 || getent hosts "${host}" >/dev/null 2>&1
}

check() {
  local name="$1"
  local url="$2"
  local attempts=12
  local delay=5
  local attempt

  for attempt in $(seq 1 "${attempts}"); do
    echo -n "Checking ${name}: ${url} (${attempt}/${attempts}) … "

    if curl -fsS --max-time 20 "${url}" >/dev/null; then
      echo "ok"
      return 0
    fi

    echo "not ready"

    if [[ "${attempt}" -lt "${attempts}" ]]; then
      sleep "${delay}"
    fi
  done

  echo "FAIL: ${name} did not become ready after ${attempts} attempts."
  return 1
}

check_public_or_local() {
  local public_name="$1"
  local public_url="$2"
  local local_name="$3"
  local local_url="$4"
  local host

  host="$(url_host "${public_url}")"
  if host_resolves "${host}"; then
    if check "${public_name}" "${public_url}"; then
      return 0
    fi
    echo "Public ${public_name} resolved but was not healthy; trying loopback."
  else
    echo "Skipping public ${public_name} (${public_url}): ${host} did not resolve on this machine."
  fi
  check "${local_name}" "${local_url}"
}

# HTTP 200 is not enough for these endpoints — require a JSON boolean flag.
check_json_true() {
  local name="$1"
  local url="$2"
  local flag="$3"
  local attempts=12
  local delay=5
  local attempt
  local body
  local http_code

  for attempt in $(seq 1 "${attempts}"); do
    echo -n "Checking ${name}: ${url} (${attempt}/${attempts}) … "

    body="$(curl -sS --max-time 20 -w '\n%{http_code}' "${url}" 2>/dev/null || true)"
    http_code="$(printf '%s' "${body}" | tail -n1)"
    body="$(printf '%s' "${body}" | sed '$d')"

    if [[ "${http_code}" == "200" ]] \
      && FLAG="${flag}" BODY="${body}" python3 -c 'import json,os,sys; raise SystemExit(0 if json.loads(os.environ["BODY"]).get(os.environ["FLAG"]) is True else 1)'; then
      echo "ok"
      return 0
    fi

    echo "not ready (http=${http_code:-?} body=${body:-<empty>})"

    if [[ "${attempt}" -lt "${attempts}" ]]; then
      sleep "${delay}"
    fi
  done

  echo "FAIL: ${name} did not report ${flag}=true after ${attempts} attempts."
  return 1
}

# Prefer public URLs when DNS works; otherwise loopback. Unresolved public
# names are not a service failure (the VDS often has no public zone locally).
check_public_or_local "web" "${WEB_URL}/api/health" "web-local" "${LOCAL_WEB}/api/health"
check_public_or_local "api" "${API_URL}/api/v1/health" "api-local" "${LOCAL_API}/api/v1/health"

# Bot must be gateway-connected (Redis heartbeat). Fail deploy otherwise.
check_json_true "bot connected" "${LOCAL_API}/bot/health" "connected"

# Campaign worker must publish a Redis heartbeat. Fail deploy otherwise.
check_json_true "campaign worker" "${LOCAL_API}/campaigns/worker/health" "online"

echo "Smoke checks passed for ${ENV_NAME}."
