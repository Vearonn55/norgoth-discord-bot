# Deployment Runbook — NorBot

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
4. Create `/opt/norbot/env/production.env` and `test.env` from the examples.
5. Install Nginx configs from `deploy/nginx/` and run `scripts/vds/install-certbot.sh`.
6. Create GitHub Environments `test` and `production` with secrets:
   - `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`
7. Push to `test` to trigger staging deploy; promote via PR into `main` for production.

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
