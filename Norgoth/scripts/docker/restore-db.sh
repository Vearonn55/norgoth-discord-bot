#!/usr/bin/env bash
# Restore a pg_dump -Fc file into the target environment database.
# DANGEROUS: overwrites the target DB. Requires CONFIRM_RESTORE=<db_name>.
set -euo pipefail

ENV_NAME="${1:-}"
DUMP_FILE="${2:-}"

if [[ -z "${ENV_NAME}" || -z "${DUMP_FILE}" ]]; then
  echo "Usage: $0 [production|test] /path/to/dump.dump" >&2
  exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "Dump file not found: ${DUMP_FILE}" >&2
  exit 1
fi

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
    echo "Usage: $0 [production|test] /path/to/dump.dump" >&2
    exit 1
    ;;
esac

if [[ "${CONFIRM_RESTORE:-}" != "${DB_NAME}" ]]; then
  echo "Refusing restore. Set CONFIRM_RESTORE=${DB_NAME} to proceed." >&2
  exit 1
fi

echo "Restoring ${DUMP_FILE} into ${DB_NAME} (${COMPOSE_PROJECT})…"
docker compose -p "${COMPOSE_PROJECT}" exec -T postgres \
  pg_restore --clean --if-exists -U "${POSTGRES_USER:-norbot}" -d "${DB_NAME}" < "${DUMP_FILE}"
echo "Restore complete."
