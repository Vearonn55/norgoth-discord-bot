#!/usr/bin/env bash
# Run Alembic migrations against the target Compose stack.
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
    ENV_FILE="/opt/norbot/env/production.env"
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.production.yml")
    ;;
  test)
    ENV_FILE="/opt/norbot/env/test.env"
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.test.yml")
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

: "${NORBOT_IMAGE_TAG:?NORBOT_IMAGE_TAG is required}"
: "${NORBOT_API_IMAGE:?NORBOT_API_IMAGE is required}"

echo "Running alembic upgrade head (${ENV_NAME}) with tag ${NORBOT_IMAGE_TAG}…"
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" run --rm --no-deps api \
  python -m alembic upgrade head
echo "Migrations complete."
