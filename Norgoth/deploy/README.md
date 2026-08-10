# NorBot deploy artifacts

| Path | Purpose |
|------|---------|
| `docker/` | Dockerfiles + dockerignores for api/bot/web |
| `compose.yml` | Base stack (postgres, redis, api, workers, bot, web) |
| `compose.production.yml` | Prod overlay (loopback 3000/8000, prod env) |
| `compose.test.yml` | Test overlay (loopback 3001/8001, test env) |
| `nginx/` | Host Nginx vhosts for prod + staging |
| `env/*.example` | Env templates (copy to `/opt/norbot/env/*.env`) |

See `Norgoth/docs/runbooks/deployment.md` for bring-up steps.
