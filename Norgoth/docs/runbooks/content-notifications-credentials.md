# Content Notifications — Provider API Credential Acquisition

**Retrieval date:** 2026-08-13  
**Never paste real credential values into this document, git, tickets, or chat.**

NorBot Content Notifications (CN) use **operator-owned** provider applications.
Discord guild administrators never enter Client Secrets, API keys, or Bearer tokens.

---

## 1. Purpose

This runbook tells the NorBot operator how to register applications and obtain
credentials for:

- Twitch (EventSub)
- YouTube (Data API v3 + WebSub)
- Kick (Events webhooks)
- X (app-only poll; stream deferred)
- TikTok (unsupported for arbitrary creators; documented for honesty)

Store secrets only in `/opt/norbot/env/production.env` and
`/opt/norbot/env/test.env` (mode `600`), sourced from
[`deploy/env/production.env.example`](../../deploy/env/production.env.example)
and [`deploy/env/test.env.example`](../../deploy/env/test.env.example).

---

## 2. Credential ownership

| Kind | Who owns | Examples | Storage |
|---|---|---|---|
| Operator app credentials | NorBot operator | Client ID/Secret, API key, Bearer, EventSub secret | Env files only |
| Connected creator tokens | Not used for MVP CN | User access/refresh tokens | N/A until a Connect flow ships |

Guild-scoped monitoring uses public creator IDs plus NorBot app credentials.
Do **not** request user OAuth merely because a provider offers it.

---

## 3. Production secret injection

1. Copy examples to the VDS:
   - `/opt/norbot/env/production.env`
   - `/opt/norbot/env/test.env`
2. `chmod 600` both files.
3. Fill platform variables (below). Leave blank to keep that platform unavailable.
4. Redeploy / recreate `api` and `content-worker` so they pick up env.
5. Confirm Worker Health → Content Notifications Worker is online.

Separate **test** and **production** provider apps (or at least separate webhook
URLs and secrets) whenever the provider allows.

---

## 4. Shared prerequisites

| Variable | Purpose | Secret? |
|---|---|---|
| `NORGOTH_PUBLIC_API_URL` | Public HTTPS base for webhooks | No (URL) |
| `NORGOTH_WEBHOOK_ENCRYPTION_KEY` | AES-GCM for EventSub secrets + Discord webhook tokens | **Yes** |
| `NORGOTH_DATABASE_URL` / `NORGOTH_REDIS_URL` | SoT + queue | **Yes** |
| `DISCORD_BOT_TOKEN` | Discord delivery | **Yes** |

Production callbacks (exact paths already used by the API):

| Platform | URL |
|---|---|
| Twitch EventSub | `https://api.norbot.io/webhooks/twitch/eventsub` |
| YouTube WebSub | `https://api.norbot.io/webhooks/youtube/websub` |
| Kick Events | `https://api.norbot.io/webhooks/kick/events` |

Test twin: replace host with `api.test.norbot.io`.

TLS must terminate at nginx for `api.norbot.io` / `api.test.norbot.io`.
Localhost webhook URLs are not accepted by providers.

---

## 5. Twitch

**Portal:** https://dev.twitch.tv/console  
**Docs:** https://dev.twitch.tv/docs/authentication/register-app/ · https://dev.twitch.tv/docs/eventsub/

### Steps

1. Enable **two-factor authentication** on the Twitch account that owns the app.
2. Open the Developer Console → **Applications** → **Register Your Application**.
3. Name: `NorBot` (unique). Category: Application Integration (or closest match).
4. OAuth Redirect URL: only required if you later add user OAuth. For MVP EventSub
   webhooks with app tokens you may still register a placeholder HTTPS callback
   under your API host (e.g. `https://api.norbot.io/api/v1/oauth/twitch/callback`)
   for future use — do not wire it until Phase 6.
5. Create the app → **Manage** → copy **Client ID** (public identifier).
6. **New Secret** → copy **Client Secret** once (secret).
7. Generate a random EventSub signing secret (10–100 ASCII characters). Store as
   `TWITCH_EVENTSUB_SECRET`.
8. Put into env:
   - `TWITCH_CLIENT_ID=` (safe identifier)
   - `TWITCH_CLIENT_SECRET=` (**secret**)
   - `TWITCH_EVENTSUB_SECRET=` (**secret**)
9. Ensure `NORGOTH_PUBLIC_API_URL` points at the environment receiving EventSub.
10. Restart `api` + `content-worker`. Add a Twitch account in CN on a test guild.
11. Confirm EventSub subscriptions for `stream.online` and `stream.offline`.
12. Go live briefly on a test channel and verify Discord delivery.

### Rotation / revoke

- Rotating Client Secret invalidates app tokens immediately — update env then restart.
- Rotating EventSub secret requires recreating subscriptions (delete old, create new).
- To disable Twitch CN: clear the three env vars and restart.

### Verification checklist

- [ ] 2FA enabled  
- [ ] Client ID/Secret in env (prod and test as appropriate)  
- [ ] EventSub callback reachable over HTTPS  
- [ ] Stream online + offline notification observed  

---

## 6. YouTube / Google

**Portal:** https://console.cloud.google.com/  
**Docs:** https://developers.google.com/youtube/v3/getting-started · https://developers.google.com/youtube/v3/guides/push_notifications

### Steps

1. Create or select a Google Cloud project (separate projects for test/prod recommended).
2. Enable **YouTube Data API v3**.
3. Credentials → **API key** → restrict to YouTube Data API v3 and (optionally) IP /
   HTTP referrer as appropriate for server-side use.
4. Store as `YOUTUBE_API_KEY=` (**secret**).
5. Do **not** use a Google service account for YouTube user data (unsupported).
6. OAuth consent screen / OAuth client: **not required** for MVP public channel
   resolve + WebSub. Add only if a future Connect-YouTube product needs private scopes
   (triggers Google app verification for sensitive scopes).
7. WebSub callback (no API key needed for hub subscribe):
   `https://api.norbot.io/webhooks/youtube/websub`
8. Restart services. Resolve a public channel and confirm WebSub lease + upload notify.
9. Quota: default **10,000 units/day**. Prefer WebSub (0 units). Avoid `search.list`
   (100 units). Prefer `channels.list` / `videos.list` (low units).

### Rotation / revoke

- Rotate API key in Cloud Console → update env → restart.
- To disable: clear `YOUTUBE_API_KEY` (resolve/enrich fails closed; WebSub can still
  receive if leases exist — unsubscribe via worker/account delete).

### Verification checklist

- [ ] API enabled  
- [ ] Key restricted  
- [ ] Channel resolve without HTML scraping  
- [ ] Upload notification via WebSub  

---

## 7. Kick

**Portal:** https://kick.com/settings/developer  
**Docs:** https://docs.kick.com/ · https://docs.kick.com/events/introduction · https://docs.kick.com/getting-started/generating-tokens-oauth2-flow

### Steps

1. Sign in with the production Kick account for NorBot.
2. Open **Developer** settings → create / edit the NorBot application.
3. Copy **Client ID** (identifier) and **Client Secret** (**secret**).
4. **Enable Webhooks** → set Webhook URL exactly:
   - Prod: `https://api.norbot.io/webhooks/kick/events`
   - Test: `https://api.test.norbot.io/webhooks/kick/events`
5. Store:
   - `KICK_CLIENT_ID=`
   - `KICK_CLIENT_SECRET=` (**secret**)
6. MVP uses **client_credentials** (app access token) to subscribe with
   `broadcaster_user_id`. User OAuth 2.1 + PKCE is **not** required for livestream
   status monitoring.
7. Restart services. Add a Kick creator; confirm `livestream.status.updated`
   subscription and live/offline Discord posts.

### Rotation / revoke

- New Client Secret → update env → restart.
- Disable webhooks in the Kick portal to stop deliveries immediately.

### Verification checklist

- [ ] Webhook URL matches environment  
- [ ] App token can create event subscriptions  
- [ ] Signature verification accepts Kick deliveries  

---

## 8. TikTok (unsupported for arbitrary creators)

**Portal:** https://developers.tiktok.com/  
**Docs:** https://developers.tiktok.com/doc/display-api-get-started · https://developers.tiktok.com/doc/webhooks-overview

### Honest limitation

TikTok Display API and Content Posting webhooks require **creator Login Kit OAuth**
and expose **that user’s** videos / app-driven publishes. There is **no** approved
API to monitor arbitrary public creators’ new posts for Discord guild alerts.

NorBot keeps TikTok **unavailable** (`is_available()=False`, active quota `0`).
Do not enable a silent scrape fallback.

### If product later wants “Connect your TikTok” (self-only)

1. Create a TikTok Developer app; complete Sandbox → Production review.
2. Enable Login Kit + Display API; request minimal scopes
   `user.info.basic` and `video.list`.
3. Verify domain/URL properties as required by TikTok.
4. Register OAuth redirect under `/api/v1/oauth/tiktok/callback` (Phase 6).
5. Store Client Key / Client Secret in env **only after** Connect flow ships.
6. Never claim arbitrary-creator monitoring.

---

## 9. X (Twitter)

**Portal:** X Developer Console (https://developer.x.com/ — confirm current URL in browser)  
**Docs:** https://docs.x.com/ (verify live; automated fetches may be blocked)

### Steps

1. Create / verify developer account → Project → App for NorBot (separate test/prod).
2. Generate **API Key** / **API Key Secret** (secrets) and **Bearer Token** (secret).
3. Store Bearer as `X_API_BEARER_TOKEN=` (code also accepts `TWITTER_BEARER_TOKEN`).
4. **Verify current pricing and access tier in the Developer Console** before scaling.
   Public commentary describes pay-per-use Post reads and tier gates for Filtered Stream /
   Activity — treat console truth as authoritative.
5. Set soft budget (optional but recommended):
   - `X_MONTHLY_READ_BUDGET=` integer max metered reads this UTC month (e.g. `5000`)
   - Leave empty / `0` to disable the soft circuit (not recommended in production).
6. MVP transport is **bounded official poll** only. Do **not** enable Filtered Stream
   or Activity webhooks until budget and tier are approved.
7. Restart services; resolve a public username; confirm poll delivery and budget counters.

### Rotation / revoke

- Regenerate Bearer in console → update env → restart.
- To halt spend: clear Bearer and/or set `X_MONTHLY_READ_BUDGET=1` then restart.

### Verification checklist

- [ ] Bearer works for `users/by/username`  
- [ ] Console pricing reviewed  
- [ ] Monthly budget set  
- [ ] No Filtered Stream consumer running  

---

## 10. Cross-platform verification

After filling credentials:

1. `GET https://api.norbot.io/content-notifications/platforms` (operator session) —
   expected `available: true` for platforms with creds; TikTok remains false.
2. Worker Health shows Content Notifications online.
3. Create one subscription per enabled platform on a private test guild.
4. Confirm Discord delivery and no token leakage in API/worker logs.

---

## 11. Official links (retrieval 2026-08-13)

| Platform | Links |
|---|---|
| Twitch | https://dev.twitch.tv/docs/authentication/register-app/ · https://dev.twitch.tv/docs/eventsub/manage-subscriptions/ |
| YouTube | https://developers.google.com/youtube/v3/getting-started · https://developers.google.com/youtube/v3/guides/push_notifications |
| Kick | https://docs.kick.com/ · https://docs.kick.com/events/introduction · https://docs.kick.com/getting-started/generating-tokens-oauth2-flow |
| TikTok | https://developers.tiktok.com/doc/display-api-get-started · https://developers.tiktok.com/doc/webhooks-overview |
| X | https://docs.x.com/ · https://docs.x.com/fundamentals/developer-apps · https://docs.x.com/x-api/fundamentals/rate-limits |
