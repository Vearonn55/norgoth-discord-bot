#!/usr/bin/env bash
# Guarded prod → sanitized → norbot_test re-hydration.
# Prefer running on the VDS so prod dumps never leave the host unencrypted.
set -euo pipefail

CONFIRM="${CONFIRM_REHYDRATE:-}"
if [[ "${CONFIRM}" != "norbot_test" ]]; then
  echo "Refusing. Set CONFIRM_REHYDRATE=norbot_test to proceed." >&2
  exit 1
fi

PROD_PROJECT="${NORBOT_COMPOSE_PROJECT_PROD:-norbot-prod}"
TEST_PROJECT="${NORBOT_COMPOSE_PROJECT_TEST:-norbot-test}"
PROD_DB="${NORBOT_PROD_DB:-norbot_prod}"
TEST_DB="${NORBOT_TEST_DB:-norbot_test}"
WORK_DIR="${NORBOT_REHYDRATE_WORKDIR:-/opt/norbot/backups/rehydrate}"
mkdir -p "${WORK_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="${WORK_DIR}/prod_${STAMP}.dump"

# Fail closed on prod-looking target identifiers.
TARGET_URL="${NORGOTH_DATABASE_URL:-}"
if [[ -n "${TARGET_URL}" ]]; then
  if [[ "${TARGET_URL}" == *"${PROD_DB}"* && "${TARGET_URL}" != *"${TEST_DB}"* ]]; then
    echo "Refusing: NORGOTH_DATABASE_URL appears to point at production (${PROD_DB})." >&2
    exit 1
  fi
  if [[ "${TARGET_URL}" == *"norbot_prod"* ]]; then
    echo "Refusing: URL contains norbot_prod." >&2
    exit 1
  fi
fi

echo "[1/5] Dumping ${PROD_DB} from ${PROD_PROJECT}…"
docker compose -p "${PROD_PROJECT}" exec -T postgres \
  pg_dump -Fc -U "${POSTGRES_USER:-norbot}" -d "${PROD_DB}" > "${DUMP}"

echo "[2/5] Recreating ${TEST_DB} in ${TEST_PROJECT}…"
docker compose -p "${TEST_PROJECT}" exec -T postgres \
  psql -U "${POSTGRES_USER:-norbot}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TEST_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${TEST_DB};
CREATE DATABASE ${TEST_DB} OWNER ${POSTGRES_USER:-norbot};
SQL

echo "[3/5] Restoring dump into ${TEST_DB}…"
docker compose -p "${TEST_PROJECT}" exec -T postgres \
  pg_restore --clean --if-exists -U "${POSTGRES_USER:-norbot}" -d "${TEST_DB}" < "${DUMP}" || true

echo "[4/5] Sanitizing secrets and PII in ${TEST_DB}…"
docker compose -p "${TEST_PROJECT}" exec -T postgres \
  psql -U "${POSTGRES_USER:-norbot}" -d "${TEST_DB}" -v ON_ERROR_STOP=1 <<'SQL'
-- Best-effort scrub of high-risk secrets and residual PII if columns exist.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'platform_credentials'
  ) THEN
    EXECUTE 'UPDATE platform_credentials SET encrypted_secret = NULL WHERE true';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'content_notification_subscriptions'
      AND column_name = 'webhook_token_encrypted'
  ) THEN
    EXECUTE 'UPDATE content_notification_subscriptions SET webhook_token_encrypted = NULL WHERE true';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'discord_managed_webhooks'
      AND column_name = 'encrypted_webhook_token'
  ) THEN
    EXECUTE 'UPDATE discord_managed_webhooks SET encrypted_webhook_token = E''\\x00'' WHERE true';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'verification_attempts'
      AND column_name = 'ip_encrypted'
  ) THEN
    EXECUTE 'UPDATE verification_attempts SET ip_encrypted = E''\\x00'', ip_hash = repeat(''0'', 64) WHERE true';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'campaigns'
      AND column_name = 'audience'
  ) THEN
    EXECUTE 'UPDATE campaigns SET audience = jsonb_build_object() WHERE true';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'campaign_recipient_results'
  ) THEN
    EXECUTE 'TRUNCATE campaign_recipient_results';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'campaign_unsubscribes'
  ) THEN
    EXECUTE 'TRUNCATE campaign_unsubscribes';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'ticket_transcripts'
  ) THEN
    EXECUTE 'TRUNCATE ticket_transcripts';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'ticket_share_tokens'
  ) THEN
    EXECUTE 'TRUNCATE ticket_share_tokens';
  END IF;
END $$;
SQL

echo "[5/5] Running migrations on test stack…"
export NORBOT_IMAGE_TAG="${NORBOT_IMAGE_TAG:?set NORBOT_IMAGE_TAG}"
export NORBOT_API_IMAGE="${NORBOT_API_IMAGE:?set NORBOT_API_IMAGE}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/migrate.sh" test

rm -f "${DUMP}"
echo "Re-hydration complete for ${TEST_DB}."
