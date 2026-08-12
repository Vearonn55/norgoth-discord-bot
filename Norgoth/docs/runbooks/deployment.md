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
