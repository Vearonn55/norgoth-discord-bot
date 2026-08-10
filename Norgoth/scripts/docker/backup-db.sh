#!/usr/bin/env bash
# Create a compressed Postgres custom-format dump for the target environment.
set -euo pipefail

ENV_NAME="${1:-production}"
BACKUP_ROOT="${NORBOT_BACKUP_ROOT:-/opt/norbot/backups/postgres}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${BACKUP_ROOT}"

case "${ENV_NAME}" in
  production)
    COMPOSE_PROJECT="${NORBOT_COMPOSE_PROJECT_PROD:-norbot-prod}"
    DB_NAME="${POSTGRES_DB:-norbot_prod}"
    ;;
  test)
    COMPOSE_PROJECT="${NORBOT_COMPOSE_PROJECT_TEST:-norbot-test}"
    DB_NAME="${POSTGRES_DB:-norbot_test}"
    ;;
  *)
    echo "Usage: $0 [production|test]" >&2
    exit 1
    ;;
esac

OUT="${BACKUP_ROOT}/${DB_NAME}_${STAMP}.dump"
echo "Backing up ${DB_NAME} from project ${COMPOSE_PROJECT} → ${OUT}"

docker compose -p "${COMPOSE_PROJECT}" exec -T postgres \
  pg_dump -Fc -U "${POSTGRES_USER:-norbot}" -d "${DB_NAME}" > "${OUT}"

# Retain 14 days locally.
find "${BACKUP_ROOT}" -type f -name "${DB_NAME}_*.dump" -mtime +14 -delete || true

echo "Backup written: ${OUT}"
echo "${OUT}"
