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
7. Optional: create `/opt/norbot/env/ghcr.pull.token` (mode 600) with a GHCR
   **pull-only** credential (`packages:read`) for **manual** `docker pull` /
   `rollback-app.sh` on the host. CI deploy logs in with a job-scoped
   `GITHUB_TOKEN` (`GHCR_PULL_TOKEN`) and logs out after `compose pull`/`up`,
   so this file is not required for GitHub Actions deploys.
8. Push to `test` to trigger staging deploy; promote via PR into `main` for production.

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
2. SCP compose + docker scripts into `/var/tmp/norbot-git-<run_id>` (not `/tmp`;
   drone-scp `rm: true` on a shared `/tmp` path races with tmpfiles cleanup and
   overlapping prod/test deploys)
3. SSH → pre-deploy `backup-db.sh production`
4. `migrate.sh production`
5. `docker compose … up -d`
6. `smoke-check.sh production`
7. `record-release.sh <sha> production`

## Local image build (optional)

```bash
cp Norgoth/deploy/docker/.dockerignore.api Norgoth/apps/api/.dockerignore
docker build -f Norgoth/deploy/docker/Dockerfile.api -t norbot-api:local Norgoth/apps/api
```

## Health endpoints

- `GET https://www.norbot.io/api/health`
- `GET https://api.norbot.io/api/v1/health` (includes `release_sha` when set)
- Bot/worker heartbeat routes via API

Provider API credential acquisition for Content Notifications:
[`docs/runbooks/content-notifications-credentials.md`](content-notifications-credentials.md).

## Smoke: Worker Health APIs, Content Notifications, Top Trending

After deploy (or when validating WH / CN / feed closeout), confirm. System UI pages were removed; use APIs/Redis for worker checks.

### Worker Health (API)

1. Compose has four worker processes: `campaign-worker`, `content-worker`, `rss-worker`, `bot`.
2. `GET /observability/workers/health` reports workers online (campaign may be **paused** if queue is paused).
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

1. With any Top Trending channel configured, the shared **Feed Refresh Interval** slider (1–12h, default 4) is editable and applies to Daily/Weekly/Monthly/All-time.
2. Interval outside 1–12 → API `invalid_daily_refresh_interval`.
3. Changing the interval recomputes each window’s `next_refresh_at` on the shared hourly grid without an immediate rebuild.
4. Eligibility is rolling at refresh time `T`: Daily `T-24h`, Weekly `T-7d`, Monthly `add_calendar_months(T,-1)`, All-time no age cutoff. A message older than 7 days must leave Weekly on the next Weekly rebuild.
5. Countdown in the panel follows backend `remaining_seconds` / `next_refresh_at` (not FE-only math).
6. Bot refresh loop hits `feed-refresh-window` for due windows; Repair still runs full `feed-repair`.

### Deploy / rollback (Top Trending + System UI)

1. Deploy API (shared interval default 4 + rolling bounds + shared schedule) before or with bot.
2. Deploy web (topbar grid fix + System UI removal + Feed Refresh Interval slider).
3. Deploy bot.
4. Rollback web alone restores System/topbar UI; API merge remains backward-compatible for legacy daily hours. Rolling bounds are a behavior change — revert API to restore calendar windows if needed.

## Security hardening (production operator actions)

Do these on the VDS after the security-hardening deploy. Details:
[`docs/security/baseline.md`](../security/baseline.md).

1. Generate `NORGOTH_INTERNAL_TOKEN` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), set it in API and bot env, restart the stack. Bot `NORGOTH_API_URL` / `NORGOTH_API_INTERNAL_URL` must stay `http://api:8000`.
2. Confirm `NORGOTH_AUTH_ENFORCED=true`, `NORGOTH_OAUTH_TOKEN_ENCRYPTION_KEY` (or webhook encryption fallback) set, `NORGOTH_ENABLE_DOCS=false`.
3. Install/reload Nginx from `deploy/nginx/` (`/internal/` deny, `limit_req`, default_server).
4. Optional: set `REDIS_PASSWORD` (URL-safe) and `NORGOTH_REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0` (staging may use DB `1`). Compose starts Redis without AUTH when the var is unset so deploys are not blocked. After you add it, rolling restart enables Redis AUTH.
5. Set `NORGOTH_PLATFORM_ADMIN_IDS` only if global campaign queue pause/resume is needed.
6. After internal-token cutover, rotate the Discord bot token if it was ever used as the public API secret.
7. Rotate Discord client secret / webhook secrets if git history may have contained them.
8. Optional: `/opt/norbot/env/ghcr.pull.token` (pull-only) for manual host pulls.
   CI deploys pass a job-scoped `GITHUB_TOKEN` as `GHCR_PULL_TOKEN` and
   `docker logout` afterward — do not persist that job token as a host file.
9. Smoke: OAuth login, guild selector, one campaign on an owned guild only, verification IP path behind Nginx.

`ssl_reject_handshake` on the HTTPS catch-all requires Nginx 1.19.4+. If `nginx -t` fails on an older package, comment that `server` block and keep the HTTP `default_server`.

