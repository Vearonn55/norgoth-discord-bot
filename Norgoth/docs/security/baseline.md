# NorBot security baseline

This document is the operator-facing baseline after the 2026 security hardening
program. It describes current controls, required production settings, and
residual risk. It is not a pentest report.

## Trust boundaries

- Browsers talk to Nginx (`www.norbot.io`, `api.norbot.io`).
- Nginx proxies to loopback-published `web:3000` and `api:8000`.
- The dashboard rewrites `/norgoth-api` to the API on the same origin.
- The Discord bot and workers call the API on the Compose network (`http://api:8000`),
  never the public `api.norbot.io` hostname for `/internal/` routes.
- Nginx denies public `/internal/`. Internal callers use `NORGOTH_INTERNAL_TOKEN`
  (`X-Norgoth-Internal-Token`). The Discord bot token is dual-accepted only
  during cutover.

## Authentication and authorization

- Operators sign in with Discord OAuth (`identify` + `guilds`). Session cookie
  `norgoth_session` is HttpOnly, SameSite=Lax, Secure in production.
- Session IDs are never returned in JSON (`/sessions/me` and public session
  payloads omit `session_id`).
- Guild-scoped APIs require Manage Guild / Administrator / owner via Discord.
- Campaigns are guild-scoped the same way. Global campaign queue
  pause/resume/rehydrate requires `NORGOTH_PLATFORM_ADMIN_IDS`.
- Guild registration (`PUT /api/v1/guilds/{id}`) is internal-token only (bot).
- Production startup fails closed unless `NORGOTH_AUTH_ENFORCED=true`,
  `NORGOTH_ENABLE_DOCS=false`, and OAuth token encryption is configured.

## Edge and application controls

- CSRF: Origin/Referer allowlist on cookie-authenticated mutating requests.
- Uploads: session required when auth is enforced.
- Rate limits: Redis, by client IP and route class (skipped in `testing`).
- Request bodies: 2 MiB JSON, 20 MiB uploads (aligned with Nginx).
- SSRF: DNS validation plus connect-to-resolved-IP for RSS fetches.
- Client IP: `X-Real-IP` / `X-Forwarded-For` trusted only from loopback peers.
- Uvicorn `--forwarded-allow-ips=127.0.0.1`.
- Public `/bot/health` is liveness only (no guild inventory).
- Nginx: `limit_req`, unknown-Host reject, HSTS/nosniff/DENY/Referrer-Policy,
  `/internal/` deny on API vhosts.

## Secrets

| Secret | Notes |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord identity only after cutover |
| `NORGOTH_INTERNAL_TOKEN` | Bot/worker → API |
| `NORGOTH_DISCORD_CLIENT_SECRET` | OAuth |
| `NORGOTH_OAUTH_TOKEN_ENCRYPTION_KEY` | Operator Discord tokens in Redis (required in production) |
| `REDIS_PASSWORD` / `NORGOTH_REDIS_URL` | Redis AUTH |
| `/opt/norbot/env/ghcr.pull.token` | Optional GHCR pull-only PAT for **manual** host pulls (mode 600). CI deploy uses a job-scoped `GITHUB_TOKEN` and logs out. |
| IP / webhook encryption keys | Verification IPs and managed webhook tokens |

Real `*.env` files under `Norgoth/deploy/env/` are gitignored. Only
`*.env.example` may be committed.

## CI gates

- Dashboard lint/test/build, API pytest, bot pytest, Docker build
- `pip-audit` on API and bot requirements
- `npm audit --omit=dev --audit-level=critical`
- Trivy image scan (`CRITICAL`, ignore unfixed). The Node.js image's bundled
  `npm`/`yarn` trees are skipped; those are not on the dashboard runtime path.

Do not blind-upgrade dependencies. Classify findings as critical / recommended /
optional / breaking-risk before changing pins.

## Residual risk

- A compromised Discord account that can Manage Guild still has full NorBot
  admin for that guild (by design).
- The Discord bot token remains a high-value Discord secret.
- SameSite=Lax does not cover every top-level GET navigation; Origin checks
  cover mutating XHR/fetch.
- Ticket transcripts and upload URLs remain capability URLs (entropy only).
- YouTube WebSub currently has no HMAC secret on subscribe.
- Staging rehydrate scrub is best-effort; treat `norbot_test` as sensitive.
- Supply-chain zero-days and floating base image tags remain until digests
  are pinned.

## Operator checklist

Complete these on the VDS after the hardening deploy. See
[`docs/runbooks/deployment.md`](../runbooks/deployment.md).
