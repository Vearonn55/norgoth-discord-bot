#!/usr/bin/env bash
# Show Alembic current revision and recent history.
set -euo pipefail

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
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.production.yml")
    ENV_FILE="/opt/norbot/env/production.env"
    ;;
  test)
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.test.yml")
    ENV_FILE="/opt/norbot/env/test.env"
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

: "${NORBOT_IMAGE_TAG:?NORBOT_IMAGE_TAG is required}"
: "${NORBOT_API_IMAGE:?NORBOT_API_IMAGE is required}"
export NORBOT_ENV_FILE="${ENV_FILE}"

docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" up -d --wait --wait-timeout 120 postgres

echo "=== alembic current (${ENV_NAME}) ==="
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" run --rm --no-deps api python -m alembic current
echo "=== alembic history (last 15) ==="
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" run --rm --no-deps api python -m alembic history -r -15:current
