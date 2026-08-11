# Data durability notes (Phase 0)

## Campaigns

- Postgres is the durable source of truth for:
  - campaign state and counters (`campaigns`)
  - campaign activity history (`campaign_activity`)
  - DM unsubscribe records (`campaign_unsubscribes`)
- Redis remains the runtime accelerator for:
  - campaign cache entries
  - execution queue (`norgoth:campaign_execution_queue`)
  - schedule zset (`norgoth:campaign_scheduled`)
  - queue pause + worker heartbeat keys
- Rollback flag: `NORGOTH_CAMPAIGN_PG_ENABLED=false` (emergency Redis-only).
- Startup/runtime reconciliation:
  - worker rebuilds queue/schedule indexes from Postgres on start
  - operator can trigger manual rebuild via `POST /campaigns/rehydrate-runtime`
- Validation:
  - flush Redis in staging; `list_campaigns` / `get_campaign` / activity endpoints rehydrate from Postgres
  - DM unsubscribes remain effective after Redis flush
  - scheduled/queued campaigns resume after worker restart

## Tickets

- Hot open-ticket records remain in Redis for the bot UX.
- Bot dual-writes durable rows through `POST /internal/ingest/{guild_id}/ticket` on open/close (including transcript on close).
- API `GET /guilds/{id}/tickets` falls back to Postgres when Redis is empty.
- Share tokens remain Redis TTL (90 days); not a durable SoT requirement for launch.
- Sessions remain Redis-only by design (short-lived).
