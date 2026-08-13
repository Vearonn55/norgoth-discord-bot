# Configurable RSS/Atom Feeds — Technical Feasibility

| Field | Value |
| --- | --- |
| **Status** | Feasibility / research (no product implementation in this document) |
| **Research date** | 2026-08-12 |
| **Recommendation** | **Proceed with constraints** |
| **Product home** | Dashboard MESSAGES → `/messages/rss-feeds` |
| **Competitor context** | [YAGPDB RSS docs](https://help.yagpdb.xyz/docs/notifications/rss/) (feature-shape reference only) |

---

## 1. Executive recommendation

**Proceed with constraints.** NorBot already has the hard pieces for a guild-scoped “poll URL → parse → dedupe → post Discord embed” pipeline: a dedicated content-notification worker with Postgres cursors and Redis queue/heartbeat, campaign-style Redis NX claim locks, reusable `ChannelSelect` / `RoleSelect`, `build_embed_dict`, `DiscordBotClient`, and `record_audit`. YouTube’s Atom path is a useful **parse reference only**; it must not become the generic RSS implementation.

Constraints that make this shippable and safe:

1. **Formats:** RSS 2.0 + Atom only at MVP. Defer RDF/RSS 1.0, full Media RSS, and auto-discovery.
2. **Worker:** New Compose service (`rss-worker`), mirroring `content-worker` — do **not** bolt generic feed polling onto `content_notification_worker.py`.
3. **Security:** First-class SSRF module (none exists today). Block private/link-local/metadata IPs after DNS resolve; re-check redirects; size/timeouts; no XXE; sanitize HTML.
4. **Quotas:** Minimum poll interval **5 minutes**; starting cap **5 feeds per guild**.
5. **Initial sync:** Seed cursor / mark existing items seen; **do not** flood Discord with backlog on first enable.
6. **Naming clarity:** Community **Feed Channels** (`/community/feed-channels`) is **Top Trending** (upvote mirrors), **not** RSS. New UI lives under MESSAGES as **RSS Feeds**.

Capacity sketch (planning only):

> **~500 guilds × 3 feeds × 12 polls/hour ≈ 18k fetches/hour**

That load is workable with a dedicated worker, Redis schedule + NX, Postgres durable config/cursors, ETag/Last-Modified short-circuit, and per-feed backoff — not with unbounded polling or stuffing into the content-notification loop.

---

## 2. Existing NorBot compatibility

### 2.1 Content Notifications worker patterns

Path: `apps/api/app/workers/content_notification_worker.py`

Relevant patterns to **reuse conceptually**, not by merging codebases:

| Pattern | Behavior today | RSS implication |
| --- | --- | --- |
| Long-running asyncio loop | Heartbeat → pop Redis job → periodic sweeps | Same shape for `rss_worker` |
| PG cursor + `next_check_at` | `PlatformMonitorCursor` polled in batches | Per-feed `next_poll_at` (or Redis ZSET + PG mirror) |
| Dedup via last-seen id | Skip if `event.external_content_id == cursor.last_seen_content_id` | Prefer GUID → link → content hash (multi-key) |
| Failure / circuit | Failure count; open circuit after repeated errors | Per-feed and optional host-level backoff |
| Delivery via bot REST | `DiscordBotClient` + job processor | Channel message (embed) + optional role mention |
| Redis heartbeat | `norgoth:content_notifications:worker:heartbeat` | Parallel key namespace, e.g. `norgoth:rss:worker:heartbeat` |

Content notifications also use WebSub leases and platform adapters (`get_adapter`). **RSS is poll-only** and should not inherit WebSub, platform registry, or webhook sender-style complexity unless a later phase explicitly adds them.

### 2.2 Campaign Redis NX locks

Path: `apps/api/app/services/campaign_store.py`

`claim_campaign_for_execution` uses `SET key NX EX ttl` so only one worker instance executes a campaign. RSS should mirror this for **per-feed poll claims** (and optionally per-guild publish claims) so horizontal scale of `rss-worker` does not double-post:

```text
SET norgoth:rss:claim:{feed_id} <iso> NX EX <ttl>
```

Redis is the **scheduler / lock / ephemeral queue** surface; **Postgres remains durable** for configs, cursors, and published-item identity (same durability philosophy as campaigns: PG first when enabled, Redis as coordination).

### 2.3 ChannelSelect / RoleSelect

Dashboard already uses:

- `apps/dashboard/src/components/ui/channel-select.tsx`
- `apps/dashboard/src/components/ui/role-select.tsx`

Content Notifications (`accounts-panel.tsx`) and Top Trending (`feed-channels-panel.tsx`) both pick destination channels this way. RSS create/edit modal should reuse the same controls for destination channel and optional mention role (including `@everyone` if product allows — decide in open questions; YAGPDB supports role or `@everyone`).

### 2.4 `build_embed_dict`

Path: `apps/api/app/services/discord/embed_builder.py` (used by campaign worker, tickets, etc.)

RSS posts should map feed item → embed dict → `build_embed_dict` so Discord limit truncation and color parsing stay consistent. Do not invent a parallel embed serializer.

### 2.5 `DiscordBotClient`

Path: `apps/api/app/integrations/discord/bot_rest.py`

Content worker constructs `DiscordBotClient(settings.discord_bot_token, http_client)` and posts through delivery services. RSS worker should do the same for `channel_messages` create (bot token). Required Discord perms in target channel: **View Channel**, **Send Messages**, **Embed Links** (and **Mention Everyone** only if that option is offered).

### 2.6 `record_audit`

Path: `apps/api/app/services/audit.py`

Config mutations (create / update / enable / disable / delete feed) must call `record_audit` with a stable `entity_type` (e.g. `rss_feed_config`) and `action` (`create` / `update` / `delete` / `enable` / `disable`). Worker publish events are optional audit noise; prefer operational metrics/logs for successful posts, audit for human config changes.

### 2.7 YouTube Atom parse — reference only

Path: `apps/api/app/integrations/content_platforms/youtube/adapter.py`

`parse_atom_feed` / `parse_websub_atom` use `xml.etree.ElementTree` with YouTube-specific namespaces (`yt:videoId`, etc.). Useful lessons:

- Prefer ElementTree (or defusedxml) over full DOM with entity expansion.
- Namespace-aware entry iteration.
- Cap entries per parse (`[:limit]`).

**Do not** route generic RSS through the YouTube adapter or content-platform registry. Build a dedicated `rss`/`atom` parser module with a neutral item model (`id`, `title`, `link`, `published`, `summary_html`, `author`).

### 2.8 Feed Channels ≠ RSS

Sidebar (`apps/dashboard/src/components/navigation/sidebar.tsx`):

- **MESSAGES** → Content Notifications → `/messages/content-notifications`
- **COMMUNITY** → “Top Trending” → `/community/feed-channels` (icon happens to be `cilRss`)

`feed-channels-panel.tsx` ranks messages by net upvotes into Daily/Weekly/Monthly/All-Time channels. **Zero overlap** with external feed URLs. Naming in docs, UI copy, and nav must keep “RSS Feeds” vs “Top Trending” distinct.

### 2.9 No SSRF module today

There is IP utilities (`ip_protection.py`, proxycheck validation) but **no shared outbound URL fetch guard** that resolves DNS and blocks RFC1918 / link-local / metadata endpoints before HTTP. RSS (user-supplied URLs) makes this mandatory. Treat SSRF as a **blocking dependency** for MVP, not a follow-up.

---

## 3. Standards and supported-format boundary

### In scope (MVP)

| Format | Detection | Notes |
| --- | --- | --- |
| **RSS 2.0** | Root `<rss version="2.0">` / channel+item | GUID, link, title, pubDate, description |
| **Atom** | Root `<feed xmlns="http://www.w3.org/2005/Atom">` | `id`, `link[@rel=alternate]`, `title`, `updated`/`published`, `summary`/`content` |

Accept `application/rss+xml`, `application/atom+xml`, `application/xml`, `text/xml` when Content-Type is present; still sniff root element if type is generic.

### Explicitly deferred

- RDF / RSS 1.0
- Full Media RSS / iTunes podcast extensions (optional later: first enclosure URL as embed image/link)
- HTML `<link rel="alternate" type="application/rss+xml">` auto-discovery from a blog homepage
- JSON Feed
- Push protocols (WebSub for arbitrary blogs)

### Validation UX

On add/edit: perform a **safe probe fetch** (SSRF-gated) and report:

- Reachable / blocked / timeout / too large / not RSS|Atom / empty channel
- Detected format + sample title
- Do not persist if probe fails (or persist as `disabled` with error — prefer hard fail on create)

---

## 4. Product scope / MVP

### In

- Guild admins configure N feed URLs (cap 5), destination text channel, optional mention role, enable/disable, delete.
- Worker polls on interval ≥ 5 minutes (default 5–15 with jitter).
- New items post as Discord embeds (title, truncated description, link, optional feed title as footer/author).
- Initial sync skips backlog (seed seen set / watermark).
- ETag / Last-Modified conditional GET when origin supports it.
- Dedup durable in Postgres.
- Audit config changes; dashboard list + modal CRUD under MESSAGES.
- Feature flag / phased rollout (section 16).

### Out (MVP)

- Templates / sender styles / managed webhooks (Content Notifications complexity).
- Per-item custom Discord message templates (beyond a simple default embed + optional mention).
- Cross-guild feed sharing / global feed catalog.
- Keyword filters, AI summaries, digests.
- Premium tier quotas (YAGPDB: 2 free / 10 premium — NorBot can start flat at 5).
- Auto-discovery from HTML.

### Competitor shape (YAGPDB)

Per [YAGPDB RSS help](https://help.yagpdb.xyz/docs/notifications/rss/): paste feed URL, pick channel, optional role/`@everyone`, list with enable/disable/delete/edit; polling latency up to ~5 minutes; hard max active feeds. NorBot MVP should feel similarly simple, with stronger SSRF and NorBot embed/audit conventions.

---

## 5. User journeys

### 5.1 Add a feed

1. Open **MESSAGES → RSS Feeds** (`/{lang}/messages/rss-feeds`).
2. Click **Add feed**.
3. Paste HTTPS (or HTTP) feed URL; select channel; optional mention role; optional display name override.
4. Submit → API SSRF-safe probe → parse sniff → persist `rss_feed_configs` + initial cursor seed (mark current items seen, `last_success_at`, store ETag if any).
5. Toast success; list row shows enabled + next poll window.
6. Audit: `rss_feed_config` / `create`.

### 5.2 Edit / pause / resume / delete

- Edit channel, role, interval (clamped ≥ min), display name.
- Disable stops scheduling without deleting history/cursor.
- Delete removes config + item/cursor rows (or soft-delete + retain for forensics — prefer hard delete of items with config FK cascade for MVP simplicity).
- Audit each mutation.

### 5.3 Runtime publish (system)

1. Scheduler marks feed due.
2. Worker acquires NX claim.
3. Conditional GET → parse → for each **new** item (after watermark): publish embed → record item id → advance cursor.
4. On 304: bump `next_poll_at` only.
5. On errors: increment failure_count, exponential backoff, surface `last_error` on list UI.

### 5.4 Permission / failure UX

- If bot lacks channel send/embed: mark feed `error` with actionable message; do not retry every 5s.
- If feed 404/410: backoff + dashboard badge “Feed URL unreachable”.
- If guild removed bot: stop claiming feeds for that guild (detect via existing guild membership signals if available).

---

## 6. Frontend architecture

### Placement

- Sidebar group: **MESSAGES**
- Nav item: **RSS Feeds** → `/messages/rss-feeds`
- App route: `apps/dashboard/src/app/[lang]/(app)/messages/rss-feeds/page.tsx`
- Search entries: add under messages parent in `search-entries.ts` (mirror content-notifications entries)

Do **not** hang this under `/community/feed-channels`.

### UI composition (mirror Content Notifications / Top Trending panels)

1. **`PageHeader`** — title “RSS Feeds”, short description (“Post new items from RSS 2.0 / Atom feeds into a channel”).
2. **List table/cards** — feed title or URL host, channel, enabled toggle, last success / last error, next poll, actions (edit / delete).
3. **Modal (create/edit)** — URL input, `ChannelSelect`, `RoleSelect` (optional), interval select (presets ≥ 5m), enable checkbox, probe status.
4. **Embed reuse** — live preview using existing Discord message preview / embed draft patterns if cheap; otherwise show a static “sample embed” from last probe item. Prefer reusing embed preview components already used for campaigns / embed library rather than a one-off.
5. **Store** — `rss-feeds-store.ts` (Zustand pattern like `content-notifications-store` / `feed-channels-store`): list, upsert, delete, toggle.

### API surface (dashboard → API)

Suggested REST under guild scope (shape only):

```text
GET    /guilds/{guild_id}/rss-feeds
POST   /guilds/{guild_id}/rss-feeds          # body includes url; server probes
PATCH  /guilds/{guild_id}/rss-feeds/{id}
DELETE /guilds/{guild_id}/rss-feeds/{id}
POST   /guilds/{guild_id}/rss-feeds/probe    # optional explicit probe without save
```

AuthZ: same guild manage permissions as Content Notifications / campaign config.

---

## 7. Backend and worker architecture

### Recommendation: **new Compose service** mirroring `content-worker`

In `deploy/compose.yml` today:

- `campaign-worker` → `python -m app.workers.campaign_worker`
- `content-worker` → `python -m app.workers.content_notification_worker`

Add:

```yaml
rss-worker:
  image: ${NORBOT_API_IMAGE:-norbot-api}:${NORBOT_IMAGE_TAG:-local}
  command: ["python", "-m", "app.workers.rss_feed_worker"]
  healthcheck: { disable: true }
  # same env_file / DATABASE / REDIS / depends_on as content-worker
```

**Why not extend content-worker?**

- Different domain model (arbitrary URLs + SSRF vs platform adapters + WebSub).
- Different failure modes and rate limits (host politeness vs YouTube/Twitch APIs).
- Independent scale/restart; content outages must not stop RSS and vice versa.
- Avoid growing an already multi-responsibility loop (jobs + poll + WebSub renew).

### Suggested module layout (implementation later)

```text
apps/api/app/
  workers/rss_feed_worker.py
  services/rss/
    scheduler.py          # Redis ZSET due + NX claim
    fetcher.py            # SSRF-safe HTTP + conditional GET
    parser.py             # RSS 2.0 + Atom → FeedItem
    dedupe.py             # GUID → link → hash
    publisher.py          # build_embed_dict + DiscordBotClient
    quotas.py             # min interval, max feeds/guild
  security/ssrf.py        # NEW shared module
  models/rss_feeds.py
  api/v1/rss_feeds.py
```

### Coordination model

| Layer | Role |
| --- | --- |
| **Postgres** | Durable configs, cursors/items, last_error, etag, next_poll_at |
| **Redis** | Due schedule ZSET (optional acceleration), per-feed NX claim, worker heartbeat, optional publish queue |
| **rss-worker** | Claim → fetch → parse → dedupe → publish → persist |
| **API** | CRUD, probe, quota enforcement, audit |

If Redis is briefly down: worker can fall back to PG `SELECT … WHERE next_poll_at <= now() FOR UPDATE SKIP LOCKED` (campaign/content durability lessons). Prefer implementing **PG as source of truth for due feeds** and Redis NX as multi-instance mutex.

### nginx

**Unchanged.** No new public routes beyond existing API reverse proxy. Outbound fetches originate from `rss-worker` / API (probe), not from browsers.

---

## 8. Suggested data model (conceptual)

> Do **not** invent migration IDs as already applied. Below is conceptual schema for a future Alembic revision.

### `rss_feed_configs`

| Column | Type (conceptual) | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `guild_id` | TEXT NOT NULL | Discord snowflake |
| `feed_url` | TEXT NOT NULL | Canonical stored URL (normalized) |
| `feed_url_hash` | BYTEA/TEXT | Unique with guild for dup URL prevention |
| `display_name` | TEXT NULL | Override; else channel/feed title |
| `channel_id` | TEXT NOT NULL | Destination |
| `mention_role_id` | TEXT NULL | Optional; special sentinel for everyone if allowed |
| `enabled` | BOOL NOT NULL DEFAULT true | |
| `poll_interval_seconds` | INT NOT NULL | ≥ 300 |
| `format_hint` | TEXT NULL | `rss20` / `atom` after probe |
| `etag` | TEXT NULL | |
| `last_modified` | TEXT NULL | Raw header value |
| `next_poll_at` | TIMESTAMPTZ | |
| `last_success_at` | TIMESTAMPTZ NULL | |
| `last_error` | TEXT NULL | |
| `failure_count` | INT NOT NULL DEFAULT 0 | |
| `created_at` / `updated_at` | TIMESTAMPTZ | |
| `created_by` | UUID NULL | discord_users FK if available |

Indexes: `(guild_id)`, `(enabled, next_poll_at)`, unique `(guild_id, feed_url_hash)`.

### `rss_feed_cursors` **or** `rss_feed_items`

Two viable shapes:

**A. Cursor watermark (lighter)**  
`rss_feed_cursors`: `feed_id`, `last_item_key`, `last_published_at`, `bootstrap_completed_at`.

**B. Item set (safer dedupe)** — **recommended for MVP**  
`rss_feed_items`:

| Column | Notes |
| --- | --- |
| `id` | UUID PK |
| `feed_id` | FK → configs ON DELETE CASCADE |
| `item_key` | Stable dedupe key (see §9) |
| `published_at` | Nullable |
| `first_seen_at` | |
| `posted_message_id` | Discord message snowflake if posted |
| `skipped_reason` | e.g. `bootstrap` |

Unique `(feed_id, item_key)`. Retain last N keys (e.g. 500) or TTL prune older than 90 days to bound growth.

Bootstrap: on first successful parse, insert current items with `skipped_reason='bootstrap'` and **do not** publish.

---

## 9. Scheduling and deduplication

### Schedule

- Default interval: **300s** (align with YAGPDB “up to 5 minutes”).
- Add jitter (±30–60s) to avoid thundering herd across ~18k fetches/hour peaks.
- After success: `next_poll_at = now + interval + jitter`.
- After failure: `min(interval * 2^n, cap)` e.g. cap 1–6 hours; reset on success.
- Disable: leave `next_poll_at` null or far future; worker skips `enabled=false`.

### Deduplication key precedence

For each entry, compute `item_key`:

1. **GUID / Atom `id`** (normalized, stripped) if present and non-empty  
2. Else **canonical link** (prefer alternate link; lowercase scheme/host; strip fragments)  
3. Else **hash** of `(title|published|summary_prefix)` — SHA-256 hex truncate

Never rely on list position alone. Content Notifications’ single `last_seen_content_id` is insufficient for feeds that reorder or edit items; prefer **set membership** of recent keys.

### Conditional HTTP

Send `If-None-Match` / `If-Modified-Since` when stored. On **304**: no parse, schedule next, clear transient errors. On **200**: update stored validators from response headers.

### Initial sync / backlog policy

**Mandatory:** first successful fetch after create (or after URL change) marks all currently present items as seen without Discord posts. Only items appearing on **subsequent** polls publish. Document this in UI helper text (“Existing items won’t be posted”).

### Capacity math (planning)

| Factor | Value |
| --- | --- |
| Guilds (planning) | ~500 |
| Feeds / guild (avg) | 3 |
| Polls / hour / feed | 12 (5‑min interval) |
| **Fetches / hour** | **≈ 18 000** |
| Avg body if 50 KB | ~900 MB/hour inbound (upper sketch) |
| With ETag 304 rate 40% | ~10.8k full downloads/hour |

Mitigations: interval floor, guild cap, shared host politeness delay, 304s, response size cap, worker concurrency limit (e.g. 10–20 in-flight fetches).

---

## 10. SSRF and parser security

**Blocking MVP requirement.** Implement a shared `app/security/ssrf.py` (or `app/services/http_safe.py`) used by probe + worker.

### Fetch policy

| Control | Rule |
| --- | --- |
| Schemes | `http` / `https` only |
| DNS | Resolve hostname; **reject** if any A/AAAA is private, loopback, link-local, ULA, multicast, or cloud metadata (`169.254.169.254`, etc.) |
| Redirects | Re-validate scheme + resolved IPs **per hop**; max hops (e.g. 3–5) |
| Bind | Connect to resolved public IP only (pin host header carefully if needed) |
| Timeouts | Connect + total read timeouts (e.g. 5s / 15s) |
| Size | Hard max body (e.g. 2–5 MiB); stream and abort |
| Ports | Allow 80/443 only (or reject non-default unless allowlisted) |
| Credentials | Reject URLs with embedded userinfo |

### Parser policy

- Prefer **defusedxml** or ElementTree with entity expansion disabled; **no XXE**.
- Do not resolve external DTDs.
- Cap entry count processed per poll (e.g. 50).
- HTML in `description` / `content`: **sanitize** to plain text or tightly allowlisted tags before Discord; strip scripts/event handlers; truncate to embed limits via `build_embed_dict`.
- Treat feed XML as untrusted; never `eval` or execute processing instructions.

### Probe path

API create/probe must use the **same** SSRF fetcher as the worker. Unit-test private IP rejects, redirect-to-private, huge body, slow loris timeout.

---

## 11. Discord publishing behavior

### Message shape (MVP)

- Optional content line: role mention (`<@&id>` or `@everyone` if enabled and permitted).
- Embed via `build_embed_dict`:
  - **title**: item title (truncated)
  - **url**: item link
  - **description**: sanitized summary (truncated)
  - **author** or **footer**: feed display name / feed title
  - **timestamp**: item published if parseable
  - **color**: fixed NorBot brand or configurable later

### Ordering

Publish oldest-new-first within a poll batch so channel chronology matches publication time when multiple items appear between polls. Cap posts per poll (e.g. 3–5) to avoid spam; retain overflow keys as “seen but not posted” **or** queue remainder — prefer **cap + mark seen** with dashboard notice on repeated overflow (open question).

### Idempotency

Before send: ensure `item_key` not already posted. After successful Discord create: store `posted_message_id`. NX claim prevents dual workers; unique constraint prevents dual rows.

### Permissions

On 403/missing access: set `last_error`, backoff, surface in UI. Do not tight-loop.

---

## 12. Rate limits and quotas

| Quota | Starting value | Rationale |
| --- | --- | --- |
| Min poll interval | **5 minutes** | Match user expectation / YAGPDB; protect capacity |
| Max feeds / guild | **5** | Conservative vs YAGPDB free(2)/premium(10); flat for MVP |
| Max concurrent fetches / worker | 10–20 | Bound FD/CPU |
| Max posts / feed / poll | 3–5 | Anti-spam |
| Max body size | 2–5 MiB | Parser DoS |
| Per-host min spacing | optional 1–2s | Politeness when many guilds share same origin |

Enforce quotas in **API** (create/update) and re-check in **worker** (defense in depth). Capacity estimate remains labeled:

> **~500 guilds × 3 feeds × 12 polls/hour ≈ 18k fetches/hour**

---

## 13. Observability

| Signal | Mechanism |
| --- | --- |
| Worker liveness | Redis heartbeat key (mirror content-notifications); optional dashboard worker panel later |
| Structured logs | `norgoth.rss.worker` — feed_id, guild_id, outcome (`304`, `posted`, `error`), latency |
| Counters | fetches, 304s, posts, parse_errors, ssrf_blocks, discord_403s |
| Per-feed state | `last_success_at`, `last_error`, `failure_count` exposed on GET list |
| Audit | Config CRUD via `record_audit` |
| Alerts (ops) | Heartbeat stale; error rate spike; fetch volume anomaly vs 18k/h baseline |

Do not log full feed bodies or mention tokens.

---

## 14. Infrastructure impact

| Component | Change |
| --- | --- |
| `deploy/compose.yml` | Add `rss-worker` service (same image/env pattern as `content-worker`) |
| `compose.production.yml` / `compose.test.yml` | Mirror service when promoting |
| Postgres | New tables via future migration (not predefined IDs here) |
| Redis | New key prefixes under `norgoth:rss:*` |
| API image | Contains worker module (same as today for campaign/content) |
| **nginx** | **Unchanged** |
| Bot process | Unchanged (REST from worker) |
| Dashboard | New route + nav only |

No new public ingress ports. Outbound HTTPS from worker network must be allowed (already required for content platforms).

---

## 15. Test strategy

### Unit

- RSS 2.0 + Atom fixtures → item fields + `item_key` precedence  
- Bootstrap marks seen / zero Discord calls  
- SSRF: private IP, DNS rebinding patterns (to the extent testable), redirect chain, oversized body  
- Sanitizer strips dangerous HTML  
- Quota validators (interval &lt; 300 rejected; 6th feed rejected)

### Integration

- API CRUD + audit rows  
- Probe success/failure  
- Worker: 200 then new item → one Discord mock post; second poll → zero posts  
- 304 path updates schedule only  
- NX claim: two workers → single publish  

### UI

- Page renders with `PageHeader`, modal validation, ChannelSelect/RoleSelect wired  
- Distinct from Top Trending copy/routes  

### Load (optional pre-prod)

- Synthetic 18k fetches/hour schedule smoke with tiny payloads and high 304 rate.

---

## 16. Rollout phases

| Phase | Scope |
| --- | --- |
| **0 — Foundations** | `ssrf` module + parser + unit tests (no UI) |
| **1 — MVP internal** | Tables, API, `rss-worker`, feature flag off externally; dogfood on internal guild |
| **2 — Dashboard** | `/messages/rss-feeds` UI; flag on for staff guilds |
| **3 — Limited GA** | Enable for all guilds; quotas 5 / 5m; monitor 18k/h envelope |
| **4 — Harden** | Host politeness, overflow policy, optional Media enclosure image, premium caps if needed |

Rollback: disable worker service + feature flag; configs remain inert.

---

## 17. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| SSRF to cloud metadata / internal net | Dedicated resolver+IP deny; redirect revalidation; ports 80/443 |
| XXE / billion laughs | defused parsing; size caps; entry caps |
| Discord spam on first add | Bootstrap skip backlog |
| Duplicate posts under scale-out | Redis NX + unique `(feed_id, item_key)` |
| Feed URL churn / unstable GUIDs | Fallback link → hash; retain item set |
| Confusion with Top Trending | Separate nav label/route; docs callout |
| content-worker overload if merged | **Separate `rss-worker`** |
| Origin rate-limits / bans | Backoff, ETag, per-host spacing, guild caps |
| Malicious HTML in descriptions | Sanitize + embed truncation |
| Capacity growth beyond 18k/h | Raise min interval or lower max feeds; scale worker replicas with PG `SKIP LOCKED` |

---

## 18. Estimated complexity by subsystem

| Subsystem | Complexity | Notes |
| --- | --- | --- |
| SSRF-safe fetcher | **High** | New security surface; must be correct |
| Parser RSS+Atom | **Medium** | Fixtures-heavy; YouTube Atom is reference only |
| Dedupe + bootstrap | **Medium** | Correctness-critical |
| PG model + API CRUD | **Medium-Low** | Familiar guild-scoped patterns |
| `rss-worker` + Redis NX | **Medium** | Mirror content/campaign patterns |
| Discord publish + embeds | **Low-Medium** | Reuse `build_embed_dict` / `DiscordBotClient` |
| Dashboard UI | **Medium-Low** | PageHeader + list + modal + selects |
| Observability / compose | **Low** | Heartbeat + one compose service |
| Media RSS / discovery / templates | **Deferred** | Not in MVP estimate |

**Overall MVP:** roughly **medium** engineering effort; **security review required** before GA because of user-controlled egress.

---

## 19. Open questions

1. Allow `@everyone` / `@here` mentions, or roles only?
2. HTTP (cleartext) feeds allowed, or HTTPS-only?
3. On URL change: treat as new feed (re-bootstrap) — confirmed?
4. Overflow policy when &gt;N new items between polls: drop-as-seen vs queue?
5. Should disable soft-retain items for re-enable without re-bootstrap?
6. Feature flag granularity: global vs per-guild entitlement?
7. Reuse Content Notification webhook “sender style”, or bot identity only for MVP? (**Recommend bot identity only.**)
8. Premium tier later (YAGPDB-style 2/10) or keep flat 5?
9. Store raw last response hash for debugging (privacy/PII in feeds)?
10. Multi-language dashboard copy ownership for new nav strings?

---

## 20. Acceptance criteria

MVP is acceptable when **all** of the following hold:

1. **Docs/product clarity:** RSS Feeds live under MESSAGES `/messages/rss-feeds`; Top Trending remains unrelated.
2. **Formats:** Valid RSS 2.0 and Atom feeds probe, store, and publish; RDF/Media/discovery not required.
3. **Quotas:** Cannot create poll interval &lt; 5 minutes or more than 5 feeds per guild.
4. **Bootstrap:** Enabling a feed never posts the pre-existing backlog.
5. **Dedupe:** Same item (GUID/link/hash) never posts twice under single or multi-worker deploy.
6. **SSRF:** Private/link-local/metadata targets and redirect-to-private are blocked in probe and worker; tests cover core cases.
7. **Parser safety:** Malicious XXE / oversized payloads fail closed without worker crash loops.
8. **Discord:** New items post via `DiscordBotClient` + `build_embed_dict` with optional role mention; missing perms surface in UI.
9. **Durability:** Configs/cursors/items in Postgres; Redis used for schedule/claims/heartbeat only.
10. **Worker isolation:** Dedicated `rss-worker` Compose service; content-worker unchanged in responsibility.
11. **Audit:** Create/update/delete/enable/disable recorded via `record_audit`.
12. **Observability:** Heartbeat + per-feed last success/error visible; nginx unchanged.
13. **Capacity posture:** Design and ops notes acknowledge **~500 guilds × 3 feeds × 12 polls/hour ≈ 18k fetches/hour** with ETag and concurrency limits.
14. **No scope creep in MVP:** No product code is implied by this document alone; implementation follows phased rollout with feature flag.

---

## References (code & external)

| Reference | Role |
| --- | --- |
| [YAGPDB RSS](https://help.yagpdb.xyz/docs/notifications/rss/) | Competitor UX/quota/polling expectations only |
| `apps/api/app/workers/content_notification_worker.py` | Worker loop / cursor poll / Discord client patterns |
| `apps/api/app/services/campaign_store.py` | Redis schedule + `SET NX` claim pattern |
| `apps/api/app/integrations/content_platforms/youtube/adapter.py` | Atom parse reference only |
| `deploy/compose.yml` | `content-worker` / `campaign-worker` service template for `rss-worker` |
| `apps/dashboard/src/components/navigation/sidebar.tsx` | MESSAGES vs COMMUNITY (Top Trending) placement |
| `apps/api/app/services/discord/embed_builder.py` | `build_embed_dict` |
| `apps/api/app/integrations/discord/bot_rest.py` | `DiscordBotClient` |
| `apps/api/app/services/audit.py` | `record_audit` |

---

*End of feasibility document. Implementation is explicitly out of scope for this research task.*
