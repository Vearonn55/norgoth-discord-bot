# Incident Runbook — NorBot

## Severity guide

| Level | Examples | First actions |
|-------|----------|---------------|
| SEV1 | Site down, auth broken, data loss risk | Smoke → rollback app → page on-call |
| SEV2 | Single feature broken (campaigns/tickets) | Check logs, Redis/PG health, recent deploy |
| SEV3 | Degraded performance | Resource checks, rate limits, Discord API |

## Quick triage

```bash
docker compose -p norbot-prod ps
curl -fsS https://www.norbot.io/api/health
curl -fsS https://api.norbot.io/api/v1/health
docker compose -p norbot-prod logs --tail=200 api
docker compose -p norbot-prod logs --tail=200 bot
```

## Common responses

- **Bad deploy:** `/opt/norbot/scripts/rollback-app.sh production`
- **DB corruption / bad migration:** stop deploy; restore from pre-deploy dump (backup-restore runbook)
- **Redis flush:** feature configs + campaigns rehydrate from Postgres; ticket open metadata may be partial until bot rewrites
- **Discord outage:** wait / status page; no local fix
- **Cert expiry:** `certbot renew` + nginx reload

## Communication

- Note deploy SHA from `/opt/norbot/releases/CURRENT`
- Prefer fixing forward unless user-visible outage > smoke window
