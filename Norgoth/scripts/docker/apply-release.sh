#!/usr/bin/env bash
# Apply a GHCR image tag (git SHA) for production|test on the VDS.
#
# Usage: apply-release.sh <production|test> <sha> [staging_dir]
#
# staging_dir is the appleboy scp target (contains Norgoth/deploy and
# Norgoth/scripts/docker). When omitted, compose/scripts already on disk are
# used, unless /opt/norbot/src is a git checkout of this repo — then that SHA
# is checked out and synced first.
set -euo pipefail

ENV_NAME="${1:-}"
SHA="${2:-}"
STAGING_DIR="${3:-}"

if [[ "${ENV_NAME}" != "production" && "${ENV_NAME}" != "test" ]]; then
  echo "Usage: $0 <production|test> <sha> [staging_dir]" >&2
  exit 1
fi
if ! [[ "${SHA}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "SHA must be a 40-char lowercase git object name." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPT_ROOT="${NORBOT_OPT_ROOT:-/opt/norbot}"
SRC_DIR="${NORBOT_SRC_DIR:-${OPT_ROOT}/src}"
OWNER_RAW="${NORBOT_IMAGE_OWNER:-${GITHUB_REPOSITORY_OWNER:-vearonn55}}"
OWNER="$(echo "${OWNER_RAW}" | tr '[:upper:]' '[:lower:]')"

export NORBOT_IMAGE_TAG="${SHA}"
export NORBOT_API_IMAGE="${NORBOT_API_IMAGE:-ghcr.io/${OWNER}/norbot-api}"
export NORBOT_BOT_IMAGE="${NORBOT_BOT_IMAGE:-ghcr.io/${OWNER}/norbot-bot}"
export NORBOT_WEB_IMAGE="${NORBOT_WEB_IMAGE:-ghcr.io/${OWNER}/norbot-web}"

sync_tree() {
  local from_deploy="$1"
  local from_scripts="$2"
  rsync -a --delete "${from_deploy}/" "${OPT_ROOT}/deploy/"
  rsync -a "${from_scripts}/" "${OPT_ROOT}/scripts/"
  chmod +x "${OPT_ROOT}/scripts/"*.sh
  chmod +x "${OPT_ROOT}/scripts/"*.py 2>/dev/null || true
}

if [[ -n "${STAGING_DIR}" ]]; then
  sync_tree "${STAGING_DIR}/Norgoth/deploy" "${STAGING_DIR}/Norgoth/scripts/docker"
elif [[ -d "${SRC_DIR}/.git" ]]; then
  # ci-apply runs as norbot; /opt/norbot/src is often cloned as root.
  git -c "safe.directory=${SRC_DIR}" -C "${SRC_DIR}" fetch --depth 1 origin "${SHA}"
  git -c "safe.directory=${SRC_DIR}" -C "${SRC_DIR}" checkout --detach "${SHA}"
  sync_tree "${SRC_DIR}/Norgoth/deploy" "${SRC_DIR}/Norgoth/scripts/docker"
else
  echo "No staging dir or ${SRC_DIR} checkout; using compose/scripts already on disk."
fi

case "${ENV_NAME}" in
  production)
    ENV_FILE="${OPT_ROOT}/env/production.env"
    COMPOSE_FILES=(-f "${OPT_ROOT}/deploy/compose.yml" -f "${OPT_ROOT}/deploy/compose.production.yml")
    ;;
  test)
    ENV_FILE="${OPT_ROOT}/env/test.env"
    COMPOSE_FILES=(-f "${OPT_ROOT}/deploy/compose.yml" -f "${OPT_ROOT}/deploy/compose.test.yml")
    ;;
esac

export NORBOT_ENV_FILE="${ENV_FILE}"
cd "${OPT_ROOT}"

SCRIPTS="${OPT_ROOT}/scripts"
# Prefer freshly synced copies; fall back to this file's directory (dev/checkout).
if [[ ! -x "${SCRIPTS}/ghcr-login.sh" || ! -f "${SCRIPTS}/validate_env.py" ]]; then
  SCRIPTS="${SCRIPT_DIR}"
fi

"${SCRIPTS}/validate-env.sh" "${ENV_NAME}" "${ENV_FILE}"
"${SCRIPTS}/ghcr-login.sh"
if [[ "${ENV_NAME}" == "production" ]]; then
  "${SCRIPTS}/backup-db.sh" production
fi
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" pull
"${SCRIPTS}/migrate.sh" "${ENV_NAME}"
compose_ok=0
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" up -d --wait --wait-timeout 180 || compose_ok=1
docker logout ghcr.io >/dev/null 2>&1 || true
if [[ "${compose_ok}" -ne 0 ]]; then
  "${SCRIPTS}/dump-compose-logs.sh" "${ENV_NAME}" || true
  exit 1
fi
if ! "${SCRIPTS}/smoke-check.sh" "${ENV_NAME}"; then
  "${SCRIPTS}/dump-compose-logs.sh" "${ENV_NAME}" || true
  exit 1
fi
"${SCRIPTS}/record-release.sh" "${NORBOT_IMAGE_TAG}" "${ENV_NAME}"
