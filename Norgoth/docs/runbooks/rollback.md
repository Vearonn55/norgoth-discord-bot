# Rollback Runbook — NorBot

## App image rollback (preferred)

Does **not** reverse Alembic migrations.

```bash
/opt/norbot/scripts/rollback-app.sh production
/opt/norbot/scripts/smoke-check.sh production
```

`rollback-app.sh` reads `/opt/norbot/releases/PREVIOUS` (`SHA=…`) and recreates api/web/bot/workers on that tag.

## When to roll back

- Containers crash-loop after deploy
- Smoke checks fail (www/api health)
- Bot heartbeat missing after grace period

## What rollback does not do

- No `alembic downgrade`
- No Postgres restore

If a migration is the root cause, stop the failed deploy (leave previous images running if still healthy), fix forward with a new migration, or follow the emergency backup restore runbook.

## Drill

1. Deploy a known-good SHA; confirm CURRENT written.
2. Deploy a deliberately bad web image / config.
3. Confirm smoke fails.
4. Run `rollback-app.sh production` and re-smoke.
5. Confirm PREVIOUS SHA is serving and `release_sha` matches.
