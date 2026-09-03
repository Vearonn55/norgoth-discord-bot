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
4. Create `/opt/norbot/env/production.env` and `test.env` from the examples
   (mode 600). Staging/production **must** set `DISCORD_BOT_TOKEN` and the
   Discord OAuth trio together (`NORGOTH_DISCORD_CLIENT_ID`,
   `NORGOTH_DISCORD_CLIENT_SECRET`, `NORGOTH_DISCORD_REDIRECT_URI`). A
   leftover redirect URI with empty client values crash-loops the API;
   `apply-release.sh` now fails that in preflight instead of compose up.
5. Install Nginx configs from `deploy/nginx/` and run `scripts/vds/install-certbot.sh`.
6. Run `scripts/vds/install-ci-apply.sh` so GitHub Actions can deploy over
   HTTPS when inbound SSH is filtered. Store the printed secret as
   `DEPLOY_APPLY_SECRET` on both GitHub Environments.
7. Create GitHub Environments `test` and `production` with secrets:
   - `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PORT`, `DEPLOY_APPLY_SECRET`
   - `DEPLOY_HOST` should be an **IPv4** address (or a hostname with an A
     record). GitHub-hosted runners often stall on an unreachable IPv6/AAAA.
     Do not use a Cloudflare-proxied hostname for SSH.
   - `DEPLOY_PORT` must match the VDS SSH listen port (default **35342** from
     `setup-firewall.sh`). Required for **both** environments — without it,
     appleboy defaults to port 22 and times out (`dial tcp …:22: i/o timeout`).
8. Optional: create `/opt/norbot/env/ghcr.pull.token` (mode 600) with a GHCR
   **pull-only** credential (`packages:read`) for **manual** `docker pull` /
   `rollback-app.sh` on the host. CI deploy logs in with a job-scoped
   `GITHUB_TOKEN` (`GHCR_PULL_TOKEN`) and logs out after `compose pull`/`up`,
   so this file is not required for GitHub Actions deploys (HTTPS apply can
   use the job token in the signed POST).
9. Push to `test` to trigger staging deploy; promote via PR into `main` for production.

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
`smoke-check.sh` and `validate-env.sh`) when changing deploy scripts — Actions
call the VDS copies.

## SSH timeout from GitHub Actions

`dial tcp …: i/o timeout` / `Connection timed out` means the GitHub-hosted
runner never completed a TCP handshake to `DEPLOY_HOST:DEPLOY_PORT`. Image
push to GHCR can still succeed. Extra SSH retries will not help if the port
is filtered.

Typical causes:

1. `DEPLOY_HOST` is a **Cloudflare-proxied** hostname. SSH to a Cloudflare
   anycast IP on port 35342 always times out. Set `DEPLOY_HOST` to the VDS
   **origin IPv4** (provider panel, or grey-cloud DNS).
2. Provider cloud firewall / ufw allows SSH only from your home IP. GitHub
   Actions egress from rotating Azure ranges.
3. `fail2ban` DROP of those Azure IPs (`fail2ban-client status sshd`).
4. sshd is not listening on `DEPLOY_PORT`.

### HTTPS apply fallback (port 443)

Workflows try SSH first. If that fails, they POST a short-lived HMAC request
to `https://api.norbot.io/__norbot/ci-apply` (test: `api.test.norbot.io`).
That path is served by nginx on **443** (already public) and proxied to a
loopback agent.

One-time on the VDS (from your laptop SSH, not from Actions):

```bash
# from a git checkout of this repo
sudo bash Norgoth/scripts/vds/install-ci-apply.sh
```

Then set GitHub Environment secrets `test` and `production`:

- `DEPLOY_APPLY_SECRET` — printed by the installer (same value as
  `/opt/norbot/env/ci-apply.secret`)
- `DEPLOY_APPLY_URL` — optional; defaults as above

If Cloudflare WAF sits in front of `api.norbot.io`, skip that path or it
will 403.

### HTTPS apply returns FastAPI `not_found` (HTTP 404)

Images may already be on GHCR while apply fails. A JSON body like
`{"error":{"code":"not_found",...}}` means **nginx proxied `/__norbot/ci-apply`
to the API**, not to `127.0.0.1:9277`.

From a laptop SSH session on the VDS:

```bash
# Prefer a fresh checkout so the hardened installer is present; otherwise pull main.
cd /opt/norbot/src   # or your clone
sudo bash Norgoth/scripts/vds/install-ci-apply.sh

# Expect 405 (agent rejects GET), not FastAPI 404:
curl -sI https://api.norbot.io/__norbot/ci-apply | head -1

# Apply the SHA Actions already pushed (full 40-char commit):
sudo -u norbot -H env NORBOT_IMAGE_OWNER=vearonn55 \
  /opt/norbot/scripts/apply-release.sh production <40-char-sha>
```

Then re-run the Deploy workflow, or rely on the manual apply above.

### Apply a SHA GitHub already pushed (manual)

Images for a failed deploy are on GHCR. From an SSH session that *does*
reach the box:

```bash
export NORBOT_IMAGE_TAG=<40-char-sha>
export NORBOT_IMAGE_OWNER=vearonn55
# job token is gone; use the host pull credential
# /opt/norbot/env/ghcr.pull.token  (mode 600)
sudo -u norbot -H /opt/norbot/scripts/apply-release.sh production "${NORBOT_IMAGE_TAG}"
```

If `apply-release.sh` is not on the VDS yet, copy it from
`Norgoth/scripts/docker/apply-release.sh` or run the installer above.

Then re-run **Deploy production** after HTTPS apply is installed, or rely on
the next push to `main`.

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

