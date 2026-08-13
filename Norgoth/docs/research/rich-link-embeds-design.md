# Rich Link Embeds — Design Freeze (Clean-Room)

**Research / design date:** 2026-08-12  
**Status:** Approved for MVP implementation in NorBot (no AGPL code reuse).

## Legal boundary

Upstream inspiration: [podaboutlist/linkfix-for-discord](https://github.com/podaboutlist/linkfix-for-discord) (AGPL-3.0).  
NorBot has no root LICENSE compatible with AGPL incorporation.

**Rule:** Clean-room reimplementation from documented behavior only. Do not copy source, regexes verbatim from upstream files, configs, branding, or README text. Third-party fixer domains are operational dependencies (disclose; allowlist; kill switch)—not contractually guaranteed.

## Product name and placement

- **Name:** Rich Link Embeds  
- **Route:** `/automation/rich-link-embeds`  
- **Sidebar:** AUTOMATION group  
- **Redis/PG feature key:** `rich_link_embeds`  
- **Snapshot suffix:** `rich_link_embeds`

## MVP platforms

| Platform | Match hosts (conceptual) | Rewrite host (default) |
|---|---|---|
| Twitter/X | `twitter.com`, `x.com` | `fxtwitter.com` |
| Bluesky | `bsky.app` | `bskx.app` |
| TikTok | `tiktok.com` | `vxtiktok.com` |
| Reddit | `reddit.com`, `redd.it` | `vxreddit.com` |

Deferred: Instagram, Pixiv, YouTube Shorts.

## Runtime behavior

1. Bot listens to `on_message` (Message Content intent already enabled).
2. Ignore bots, webhooks, and the NorBot user.
3. Extract http(s) URLs outside code fences / inline code.
4. For each enabled platform adapter, rewrite matching URLs (strip tracking query when safe).
5. Reply once with rewritten link(s); never edit/delete the user message.
6. Idempotency: Redis key `norgoth:guild:{id}:rich_link_embeds:seen:{message_id}` short TTL.
7. Rate limit per guild/user; max links per message (e.g. 3).
8. Optional `on_message_edit` for first-seen edits only when configured.

## Config shape (JSONB)

```json
{
  "enabled": false,
  "platforms": {
    "twitter": true,
    "bluesky": true,
    "tiktok": true,
    "reddit": true
  },
  "channel_allowlist": [],
  "channel_denylist": [],
  "ignore_bots": true,
  "process_edits": false,
  "max_links_per_message": 3,
  "rewrite_hosts": {
    "twitter": "fxtwitter.com",
    "bluesky": "bskx.app",
    "tiktok": "vxtiktok.com",
    "reddit": "vxreddit.com"
  },
  "disclosure_acknowledged": false
}
```

Empty allowlist = all channels (minus denylist).

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
