# Data durability notes (Phase 0)

## Campaigns

- Postgres is the durable source of truth via `campaign_store` dual-write.
- Redis remains cache + execution queue + schedule zset.
- Rollback flag: `NORGOTH_CAMPAIGN_PG_ENABLED=false` (emergency Redis-only).
- Validation: flush Redis in staging; `list_campaigns` / `get_campaign` rehydrate from Postgres.

## Tickets

- Hot open-ticket records remain in Redis for the bot UX.
- Bot dual-writes durable rows through `POST /internal/ingest/{guild_id}/ticket` on open/close (including transcript on close).
- API `GET /guilds/{id}/tickets` falls back to Postgres when Redis is empty.
- Share tokens remain Redis TTL (90 days); not a durable SoT requirement for launch.
- Sessions remain Redis-only by design (short-lived).
