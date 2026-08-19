# Rich Link Embeds — Design Freeze (Clean-Room)

**Research / design date:** 2026-08-12  
**Status:** Approved for MVP implementation in NorBot (no AGPL code reuse).

## Legal boundary

Upstream inspiration: [podaboutlist/linkfix-for-discord](https://github.com/podaboutlist/linkfix-for-discord) (AGPL-3.0).  
NorBot has no root LICENSE compatible with AGPL incorporation.

**Rule:** Clean-room reimplementation from documented behavior only. Do not copy source, regexes verbatim from upstream files, configs, branding, or README text. Third-party fixer domains are operational dependencies (disclose; allowlist; kill switch)—not contractually guaranteed.

## Product name and placement

- **Name (user-facing):** Link Embeds / Bağlantı Önizlemeleri  
- **Name (legacy internal docs):** Rich Link Embeds  
- **Route:** `/automation/rich-link-embeds`  
- **Sidebar:** AUTOMATION group  
- **Redis/PG feature key:** `rich_link_embeds`  
- **Snapshot suffix:** `rich_link_embeds`

## MVP platforms

See addendum (2026-08-19) for the six-platform allowlist. Original MVP shipped four platforms (Twitter/X, Bluesky, TikTok, Reddit); Instagram, Pixiv, and YouTube Shorts were added with defaults off; Bluesky was later removed from this feature.

## Runtime behavior

1. Bot listens to `on_message` (Message Content intent already enabled).
2. Ignore bots, webhooks, and the NorBot user.
3. Extract http(s) URLs outside code fences / inline code.
4. For each enabled platform adapter, rewrite matching URLs (strip tracking query when safe).
5. Reply once with rewritten link(s); never edit/delete the user message body. After a successful reply, optionally suppress original embeds when Manage Messages is available.
6. Idempotency: Redis key `norgoth:guild:{id}:rich_link_embeds:seen:{message_id}` short TTL.
7. Rate limit per guild/user; max links per message (e.g. 3).
8. Optional `on_message_edit` for first-seen edits only when configured.

## Config shape (JSONB)

```json
{
  "enabled": false,
  "platforms": {
    "twitter": true,
    "tiktok": true,
    "reddit": true,
    "instagram": false,
    "pixiv": false,
    "youtube_shorts": false
  },
  "channel_allowlist": [],
  "channel_denylist": [],
  "ignore_bots": true,
  "process_edits": false,
  "max_links_per_message": 3,
  "rewrite_hosts": {
    "twitter": "fxtwitter.com",
    "tiktok": "tnktok.com",
    "instagram": "instagram7.com",
    "reddit": "vxreddit.com",
    "pixiv": "phixiv.net",
    "youtube_shorts": "youtu.be"
  },
  "disclosure_acknowledged": false
}
```

Empty allowlist = all channels (minus denylist). `rewrite_hosts` is server-forced from the operator allowlist (not guild-editable).

## Command Center

- PageHeader + master toggle  
- Per-platform mini cards  
- Channel allow/deny  
- External-service disclosure  
- Test URL field (client-side preview of rewrite only)

## Persistence

- Postgres table `rich_link_embeds_configs` via feature_config_store pattern  
- Redis snapshot for bot read-through  
- No durable transform log in MVP (Redis seen-set only)

## Tests

Unit tests per adapter: canonical URL, query strip, unsupported domain, multiple links, code-block ignore.

---

## Addendum — Link Embeds evolution (2026-08-13)

**User-facing name:** Link Embeds / Bağlantı Önizlemeleri  
**Internal key/route unchanged:** `rich_link_embeds` / `/automation/rich-link-embeds`

### Platforms (7)

| Platform | Match hosts (conceptual) | Rewrite host (fixed allowlist) | Default |
|---|---|---|---|
| Twitter/X | `twitter.com`, `x.com` (+ mobile) | `fxtwitter.com` | prior saved / true |
| Bluesky | `bsky.app` | `bskx.app` | prior saved / true |
| TikTok | `tiktok.com`, `vm.tiktok.com` | `vxtiktok.com` | prior saved / true |
| Instagram | `instagram.com` `/p|/reel|/stories/` | `ddinstagram.com` | **false** (new) |
| Reddit | `reddit.com`, `redd.it` (skip `/s/`) | `vxreddit.com` | prior saved / true |
| Pixiv | `pixiv.net` artworks / illust_id | `phixiv.net` | **false** (new) |
| YouTube Shorts | `youtube.com/shorts/{id}` only | `youtu.be/{id}` | **false** (new) |

### Security / behavior updates

- Rewrite hosts are **operator allowlist only**; API ignores client host overrides.
- UI shows read-only target domain per card; no host editors.
- Host matching is exact (after stripping a single leading `www.`), not loose suffix match.
- After a successful bot reply, attempt original-embed suppress (`Manage Messages`); degrade quietly if denied.
- Spoiler bars on the source message wrap the reply in `||…||`.
- Mini cards: when master is on, disabled services use a red accent + “Disabled” text.

### Legal note

Same clean-room boundary as above. Fixer ToS/commercial-use claims require legal review before marketing language.

---

## Addendum — fxTikTok + Bluesky (2026-08-19)

TikTok rewrites now use hosted **fxTikTok** at `tnktok.com` (standard mode). NorBot does not vendor fxTikTok source. `vxtiktok.com` is no longer generated.

Bluesky is **removed from Link Embeds only**. `bsky.app` URLs are left untouched. Shared CoreUI icons are unchanged.

### Platforms (6)

| Platform | Match hosts (conceptual) | Rewrite host (fixed allowlist) | Default |
|---|---|---|---|
| Twitter/X | `twitter.com`, `x.com` (+ mobile) | `fxtwitter.com` | prior saved / true |
| TikTok | `tiktok.com`, `m.tiktok.com`, `vm.tiktok.com`, `vt.tiktok.com`; `/video/`, `/photo/`, `/t/`; short hosts also `/{code}` | `tnktok.com` | prior saved / true |
| Instagram | `instagram.com` `/p|/reel|/stories/` | `instagram7.com` | **false** (new) |
| Reddit | `reddit.com`, `redd.it` (skip `/s/`) | `vxreddit.com` | prior saved / true |
| Pixiv | `pixiv.net` artworks / illust_id | `phixiv.net` | **false** (new) |
| YouTube Shorts | `youtube.com/shorts/{id}` only | `youtu.be/{id}` | **false** (new) |

Emergency disable remains `platforms.tiktok` or the master `enabled` switch. There is no per-message health probe of `tnktok.com`.

**Staging smoke (manual, not CI):** with Link Embeds and TikTok on, a `tiktok.com/@user/video/{id}` message should get a bot reply on `https://tnktok.com/...`. A `bsky.app` post URL should not be rewritten.

Migration `0033_link_embeds_providers` remaps `rewrite_hosts.tiktok` from `vxtiktok.com` (or missing) to `tnktok.com`, deletes Bluesky JSON keys, and drops Redis snapshots `norgoth:guild:*:rich_link_embeds`. Downgrade disables TikTok and does **not** restore `vxtiktok.com`.

