#!/usr/bin/env bash
# Roll app containers back to the PREVIOUS immutable image SHA.
# Does NOT run alembic downgrade.
set -euo pipefail

RELEASES_DIR="${NORBOT_RELEASES_DIR:-/opt/norbot/releases}"
ENV_NAME="${1:-production}"
PREVIOUS_FILE="${RELEASES_DIR}/PREVIOUS"

if [[ ! -f "${PREVIOUS_FILE}" ]]; then
  echo "No PREVIOUS release recorded at ${PREVIOUS_FILE}" >&2
  exit 1
fi

# PREVIOUS format: SHA=<sha> TIMESTAMP=<iso> ENV=<env>
# shellcheck disable=SC1090
source "${PREVIOUS_FILE}"

if [[ -z "${SHA:-}" ]]; then
  echo "PREVIOUS file missing SHA=…" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${DEPLOY_DIR_OVERRIDE:-}" ]]; then
  DEPLOY_DIR="${DEPLOY_DIR_OVERRIDE}"
elif [[ -d /opt/norbot/deploy ]]; then
  DEPLOY_DIR="/opt/norbot/deploy"
elif [[ -d "${SCRIPT_DIR}/../../deploy" ]]; then
  DEPLOY_DIR="$(cd "${SCRIPT_DIR}/../../deploy" && pwd)"
else
  DEPLOY_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)/Norgoth/deploy"
fi

case "${ENV_NAME}" in
  production)
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.production.yml")
    ;;
  test)
    COMPOSE_FILES=(-f "${DEPLOY_DIR}/compose.yml" -f "${DEPLOY_DIR}/compose.test.yml")
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

OWNER="${GITHUB_REPOSITORY_OWNER:-vearonn55}"
export NORBOT_IMAGE_TAG="${SHA}"
export NORBOT_API_IMAGE="${NORBOT_API_IMAGE:-ghcr.io/${OWNER}/norbot-api}"
export NORBOT_BOT_IMAGE="${NORBOT_BOT_IMAGE:-ghcr.io/${OWNER}/norbot-bot}"
export NORBOT_WEB_IMAGE="${NORBOT_WEB_IMAGE:-ghcr.io/${OWNER}/norbot-web}"

echo "Rolling back ${ENV_NAME} app containers to SHA=${SHA}…"
docker compose "${COMPOSE_FILES[@]}" up -d --no-deps --force-recreate \
  api campaign-worker content-worker bot web

echo "Rollback recreate issued. Run smoke-check.sh next."
