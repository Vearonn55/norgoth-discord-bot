# Norgoth — Discord Community Command Center

One unified stack: dashboard, API, Discord bot, and campaign worker.

| App | Stack | Port |
|---|---|---|
| `apps/dashboard` | Next.js 16 | 3000 |
| `apps/api` | FastAPI (campaigns via Redis + verification via Postgres) | 8000 |
| `apps/bot` | discord.py Gateway bot | — |
| `apps/api/app/workers` | Campaign delivery worker | — |

## Quick start

```bash
cp .env.example .env       # fill in DISCORD_BOT_TOKEN and OAuth secret
./scripts/dev.sh           # starts Redis, Postgres, API, worker, bot, dashboard
```

Prerequisites: Homebrew Redis + PostgreSQL 14, Python 3.14 venvs in
`apps/api/.venv` and `apps/bot/.venv` (`pip install -r requirements.txt`),
and `npm install` in `apps/dashboard`.

## Environment

Everything reads a single `Norgoth/.env` (see `.env.example`):

- `DISCORD_BOT_TOKEN` — bot login + role grants + campaign sends (required)
- `NORGOTH_DISCORD_CLIENT_ID/SECRET/REDIRECT_URI` — member verification OAuth
  (all three together, or none). Uncomment in `.env` and set the Client
  Secret; redirect must match the Discord Developer Portal. Missing config
  yields HTTP 503 (not a generic 500) on authorize.
- `NORGOTH_PUBLIC_API_URL` — optional public API base for Discord verify-panel
  link buttons (defaults to local API)
- `NEXT_PUBLIC_DASHBOARD_URL` — dashboard origin for ticket transcript links
  in close DMs (defaults to `http://127.0.0.1:3000`)
- `NORGOTH_DATABASE_URL` / `NORGOTH_REDIS_URL` — persistence
- `NORGOTH_IP_HASH_KEY` / `NORGOTH_IP_ENCRYPTION_KEY` — IP privacy keys
- `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` — optional, Twitch live
  notifications (YouTube works without keys)
- `NEXT_PUBLIC_API_BASE_URL` — dashboard → API base URL

## Modules

Each module has a master on/off slider on the Settings page, per-guild config
in Redis, a discord.py cog, FastAPI routes, and a dashboard page:

| Module | Bot cog | Dashboard page |
|---|---|---|
| Welcome & leave messages | `client.py` | Automation → Welcome & Invite Flow |
| Auto-role | `client.py` | Automation → Auto Role |
| Moderation commands (/kick, /ban, /timeout, /purge) | `moderation.py` | Security → Audit Logs |
| Auto-moderation (words, spam, invites, mentions) | `automod.py` | Security → Auto-Moderation |
| Server logging (member/message/role/channel events) | `server_logging.py` | Security → Audit Logs |
| Ticket system (panel button + private channels) | `tickets.py` | Community → Support Tickets |
| Leveling (/rank, /leaderboard, role rewards) | `leveling.py` | Community → Levels & Activity |
| Auto-responses (keyword triggers) | `autoresponder.py` | Automation → Auto-Responses |
| Role menus (self-assign buttons) + /role | `roles.py` | Automation → Self-Assignable Roles |
| Invite tracking (/invites, attribution) | `invites.py` | Community → Invite Tracking |
| Stream notifications (YouTube RSS + Twitch Helix) | `notifications.py` | Automation → Stream Notifications |
| Campaigns (channel posts + member DMs) | worker | Messages → Campaigns |

## Discord setup

1. Create the application/bot in the Discord Developer Portal; enable the
   **Server Members** and **Message Content** privileged intents (the latter
   is required for auto-moderation, auto-responses, and leveling).
2. On the **Bot** tab, leave **Requires OAuth2 Code Grant** **OFF**. NorBot
   uses a simple Guild Install (`bot` + `applications.commands`) via
   `/api/v1/oauth/discord/bot-invite`. That toggle must stay off unless you
   implement a full install-time code-grant exchange (NorBot does not).
   Login OAuth (`identify` + `guilds`) is a separate flow and does not need
   this setting.
3. Invite the bot with: Manage Roles, Kick, Ban, Moderate Members,
   Send Messages, Manage Messages, Manage Channels (tickets),
   Manage Server (invite tracking), View Channels.
4. Keep the bot's role **above** the verified/auto/reward roles.
5. Register the OAuth redirect:
   `http://127.0.0.1:8000/api/v1/oauth/discord/callback`
6. Auto-mod testing tip: staff with Manage Messages are exempt by default.
   Turn off **Exempt Manage Messages** in Auto-Moderation (or test with a
   non-privileged account). Save config before expecting rules to fire;
   master enabled defaults off until saved.

## Tests

```bash
cd apps/api && .venv/bin/python -m pytest   # verification domain (246 tests)
```

Architecture details: [`../docs/arc42.md`](../docs/arc42.md).
