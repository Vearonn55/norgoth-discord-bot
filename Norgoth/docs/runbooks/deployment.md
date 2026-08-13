# Deployment Runbook — NorBot

<!-- ci-cd smoke: 2026-08-11c -->

## Layout on the VDS

```text
/opt/norbot/
  deploy/     # compose + nginx templates (synced from repo Norgoth/deploy)
  env/        # production.env + test.env (mode 600)
  scripts/    # copies of Norgoth/scripts/docker/*.sh
  releases/   # CURRENT + PREVIOUS
  backups/postgres/
```

## First-time bring-up

1. Run `scripts/vds/bootstrap.sh` as root.
2. Run `scripts/vds/setup-firewall.sh` (defaults to SSH port **35342**;
   override with `SSH_PORT=...` if needed). Keep your current SSH session open
   and verify a second login before closing it.
3. Sync `Norgoth/deploy/` → `/opt/norbot/deploy/` and docker scripts → `/opt/norbot/scripts/`.
   Later deploys restore these from git (do not edit compose on the VDS).
4. Create `/opt/norbot/env/production.env` and `test.env` from the examples.
5. Install Nginx configs from `deploy/nginx/` and run `scripts/vds/install-certbot.sh`.
6. Create GitHub Environments `test` and `production` with secrets:
   - `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PORT`
   - `DEPLOY_PORT` must match the VDS SSH listen port (default **35342** from
     `setup-firewall.sh`). Required for **both** environments — without it,
     deploy-test defaults to port 22 and times out.
7. Push to `test` to trigger staging deploy; promote via PR into `main` for production.

## After deploy: bot online check

Smoke requires `GET {local-api}/bot/health`. If Discord still shows the bot
offline after a green deploy:

```bash
docker compose --env-file /opt/norbot/env/production.env \
  -f /opt/norbot/deploy/compose.yml \
  -f /opt/norbot/deploy/compose.production.yml \
  ps bot

docker compose --env-file /opt/norbot/env/production.env \
  -f /opt/norbot/deploy/compose.yml \
  -f /opt/norbot/deploy/compose.production.yml \
  logs bot --tail 100
```

Confirm `DISCORD_BOT_TOKEN` in `/opt/norbot/env/production.env` matches the
Developer Portal bot for the live Application ID. Look for `Bot ready` in logs.

Keep `/opt/norbot/scripts/` in sync with `Norgoth/scripts/docker/` (including
`smoke-check.sh`) when changing deploy scripts — Actions call the VDS copies.

## Normal production deploy

Triggered by push to `main` (GitHub Actions `deploy-production.yml`):

1. Build/push `norbot-{api,bot,web}:<sha>` to GHCR
2. SSH → pre-deploy `backup-db.sh production`
3. `migrate.sh production`
4. `docker compose … up -d`
5. `smoke-check.sh production`
6. `record-release.sh <sha> production`

## Local image build (optional)

```bash
cp Norgoth/deploy/docker/.dockerignore.api Norgoth/apps/api/.dockerignore
docker build -f Norgoth/deploy/docker/Dockerfile.api -t norbot-api:local Norgoth/apps/api
```

## Health endpoints

- `GET https://www.norbot.io/api/health`
- `GET https://api.norbot.io/api/v1/health` (includes `release_sha` when set)
- Bot/worker heartbeat routes via API

## Smoke: Worker Health, Content Notifications, Top Trending

After deploy (or when validating WH / CN / feed closeout), confirm:

### Worker Health

1. Compose has four worker processes: `campaign-worker`, `content-worker`, `rss-worker`, `bot`.
2. Command Center → Worker Health shows all four **online** (campaign may be **paused** if queue is paused).
3. Heartbeat keys present in Redis (TTL ~45s):
   - `norgoth:worker:heartbeat`
   - `norgoth:content_notifications:worker:heartbeat`
   - `norgoth:rss:worker:heartbeat`
   - `norgoth:bot:heartbeat` (+ `norgoth:bot:status`)
4. Legacy smoke still works: `GET …/campaigns/worker/health`, `GET …/bot/health`.

### Content Notifications limits

1. Create/enable subscriptions up to the platform active cap (YT/Twitch 10, Kick 5, X 3, TikTok 0).
2. Next create/enable over the cap returns **400** with `content_notification_limit_reached` (or total soft-cap code).
3. Dashboard capacity badges match server usage.

### Top Trending schedules

1. Configure Daily with a channel → Daily 1–12h slider is editable; without Daily channel → cadence is read-only / configure-first.
2. Daily interval outside 1–12 → API `invalid_daily_refresh_interval`; non-daily interval submit → `unsupported_refresh_interval_for_window`.
3. Enable Weekly → `next_refresh_at` ≈ `schedule_anchor_at` + 7 days (UTC).
4. Countdown in the panel follows backend `remaining_seconds` / `next_refresh_at` (not FE-only math).
5. Bot refresh loop hits `feed-refresh-window` for due windows; Repair still runs full `feed-repair`.
