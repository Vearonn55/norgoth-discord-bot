# Test DB Re-hydration Runbook — NorBot

Weekly (or manual) refresh of `norbot_test` from a consistent `norbot_prod` dump.

## Guards (fail closed)

- Requires `CONFIRM_REHYDRATE=norbot_test`
- Refuses if `NORGOTH_DATABASE_URL` looks like production / contains `norbot_prod`
- Target recreate is only `norbot_test`

## Run on VDS

```bash
export CONFIRM_REHYDRATE=norbot_test
export NORBOT_IMAGE_TAG="$(grep '^SHA=' /opt/norbot/releases/CURRENT | cut -d= -f2)"
export NORBOT_API_IMAGE=ghcr.io/<owner>/norbot-api
/opt/norbot/scripts/rehydrate-test-db.sh
```

GitHub Actions workflow `rehydrate-test-db.yml` invokes the same script over SSH (environment `test`). It must pass `secrets.DEPLOY_PORT` (not 22); otherwise the runner dials port 22 and times out before the script starts.

## Sanitization

The script nulls known secret columns when present (platform credentials / webhook tokens). Extend the SQL block as schema evolves.

## Validation

1. Dry-run without `CONFIRM_REHYDRATE` → must refuse
2. Point URL at prod identifiers → must refuse
3. Successful run → test stack migrates and is ready for staging traffic
