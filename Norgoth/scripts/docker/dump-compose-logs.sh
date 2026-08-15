#!/usr/bin/env bash
# Print Compose status and recent container logs after a failed deploy step.
# Never fails the caller — every docker command is best-effort.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d /opt/norbot/deploy ]]; then
  DEPLOY_DIR="/opt/norbot/deploy"
elif [[ -d "${SCRIPT_DIR}/../../deploy" ]]; then
  DEPLOY_DIR="$(cd "${SCRIPT_DIR}/../../deploy" && pwd)"
else
  DEPLOY_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)/Norgoth/deploy"
fi

ENV_NAME="${1:-production}"

case "${ENV_NAME}" in
  production)
    ENV_FILE="/opt/norbot/env/production.env"
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.production.yml")
    PREFIX="${NORBOT_COMPOSE_PROJECT_PROD:-norbot-prod}"
    ;;
  test)
    ENV_FILE="/opt/norbot/env/test.env"
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.test.yml")
    PREFIX="${NORBOT_COMPOSE_PROJECT_TEST:-norbot-test}"
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

echo "==== compose ps (${ENV_NAME}) ===="
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" ps -a || true

for svc in api postgres redis campaign-worker content-worker rss-worker bot web; do
  echo "==== ${svc} logs ===="
  docker logs "${PREFIX}-${svc}-1" --tail 150 || true
done
