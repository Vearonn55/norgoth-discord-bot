# YAGPDB Competitor Gap Analysis — NorBot

**Research date:** 2026-08-12  
**Audience:** Product and engineering  
**Status:** Durable research baseline (capabilities and priorities; not an implementation plan)

---

## 1. Executive summary

YAGPDB remains a strong general-purpose Discord bot: deep custom-command templating, notification feeds (YouTube, Twitch, Reddit, RSS), advanced role menus, automoderation with violation thresholds, moderation warnings/modlog depth, and a long tail of utility/fun commands. NorBot already covers a large overlapping surface—verification, tickets, leveling, invites, Top Trending feed channels, campaigns, embed library, content notifications (YouTube/Twitch live; Kick/X credential-gated; TikTok blocked), automod, raid, honeypot, welcome/leave, autorole, autoresponses, role menus, Discord/audit logs, analytics, and worker health—while differentiating on campaign messaging, verification/security posture, and curated trending feeds rather than generic RSS.

The actionable gap is narrow and high-value:

| Priority | Focus |
| --- | --- |
| **Now** | Standalone RSS feasibility (separate engineering doc); Rich Link Embeds (link embed repair / richer URL presentation) |
| **Next** | Reddit as a content-notification platform; deeper automod parity discovery; warnings and mod-history depth |
| **Later** | Polls; reminders; advanced role-menu modes beyond current give/take/toggle |
| **Reject / defer** | Arbitrary custom-command templating (sandbox/DoS surface); Cat Facts–class novelty; any AGPL copy of competitor implementation |

NorBot should not chase feature parity. Prefer durable, operator-safe capabilities that extend existing workers (`content-notification-worker`, `campaign-worker`), dashboard modules, and bot cogs—without importing AGPL-licensed design or code.

---

## 2. Research scope and source date

| Item | Detail |
| --- | --- |
| **Research date** | 2026-08-12 |
| **Primary competitor** | YAGPDB (public product docs + GitHub releases) |
| **In scope** | Public feature inventory from help center and homepage; NorBot repo evidence for presence/absence; priority recommendation with MVP boundaries |
| **Out of scope** | Implementation design for RSS (separate feasibility doc); pricing experiments; full automod rule-engine rewrite; cloning custom-command language semantics |
| **Method** | Read competitor primary URLs; map against NorBot dashboard sidebar, API routers, bot cogs, and workers; encode Now/Next/Later/Reject with acceptance signals |
| **License caution** | YAGPDB is open source under AGPL-family licensing. This document cites *capabilities* and public docs only. Do not copy branding, prose, templates, or implementation. |

---

## 3. NorBot baseline (from repo evidence)

### 3.1 Product surface (dashboard)

`apps/dashboard/src/components/navigation/sidebar.tsx` — `SIDEBAR_GROUPS`:

| Group | Modules |
| --- | --- |
| HOME | Dashboard, Analytics |
| COMMUNITY | Member Verification, Manual Verification, Support Tickets, Levels & Activity, **Top Trending** (`/community/feed-channels`), Leaderboards, Invite Tracking |
| MESSAGES | Campaigns, Create Campaign, Campaign History, Embed Library, **Content Notifications** |
| AUDIT | Audit Logs, Discord Logs |
| SECURITY | Auto-Moderation, Raid Protection, Honeypot |
| AUTOMATION | Auto Role, Welcome & Leave, Auto-Responses, Self-Assignable Roles |
| SYSTEM | Worker Health, Settings |

**Explicit absences in navigation / product intent:** standalone RSS feeds, Rich Link Embeds / link embed repair as a first-class module, arbitrary custom commands.

### 3.2 API surface

Routers registered in `apps/api/app/main.py` include (non-exhaustive of auth/OAuth): campaigns, analytics, bot, automation, moderation, modules, automod, server logs, system audit logs, tickets, verification panel, leveling, **feed channels**, autoresponder, role menus, invites, notifications, **content notifications** (+ catalog + platform webhooks), uploads, embed messages, logging config, raid, honeypot, ingest, internal config, activity.

Dashboard also exposes guild feed repair under `apps/dashboard/src/app/api/guilds/[guildId]/feed-channels/repair/route.ts` (Top Trending repair—not RSS).

### 3.3 Bot cogs

`apps/bot/bot/client.py` `setup_hook` loads: Moderation, AutoMod, ServerLogging, Analytics, Leveling, AutoResponder, Roles, Invites, Raid, Honeypot, Notifications, Campaigns, EmbedSync, FeedChannels, Tickets.

### 3.4 Workers

| Worker | Path | Role |
| --- | --- | --- |
| Content notifications | `apps/api/app/workers/content_notification_worker.py` | Poll/push platform sources via adapter registry |
| Campaigns | `apps/api/app/workers/campaign_worker.py` | Campaign delivery pipeline |

### 3.5 Content notifications platforms

`apps/api/app/routes/content_notifications.py` — `PlatformLiteral = "youtube" | "twitch" | "kick" | "x" | "tiktok"`.

`apps/api/app/integrations/content_platforms/registry.py` adapters:

| Platform | Availability (code) |
| --- | --- |
| YouTube | Adapter present; production path |
| Twitch | Adapter present; production path |
| Kick | Available only when `KICK_CLIENT_ID` / `KICK_CLIENT_SECRET` set |
| X | Available only when `X_API_BEARER_TOKEN` (or `TWITTER_BEARER_TOKEN`) set |
| TikTok | **Blocked** — no approved arbitrary-creator monitoring API (`tiktok/adapter.py`) |

**Reddit and standalone RSS are not platforms in this registry.**

### 3.6 Top Trending vs RSS

Top Trending (`feed_channels` models/routes/cog/panel) ranks and presents guild media/activity windows (daily/weekly/monthly/all-time). It is **not** an arbitrary RSS subscriber. Confusing the sidebar RSS icon with YAGPDB-style RSS would mis-state the product.

### 3.7 Adjacent baselines relevant to gaps

| Area | Evidence | Implication |
| --- | --- | --- |
| Autoresponses | `apps/bot/bot/autoresponder.py` — keyword match (contains/exact/starts_with), cooldown, simple `{user}` / `{username}` substitution | Not a template language |
| Role menus | `apps/bot/bot/roles.py` — buttons/select/reactions; modes `give` / `take` / `toggle` | Advanced exclusivity / require-role group modes are thinner than competitor |
| Automod | `apps/api/app/routes/automod.py` — words, spam, duplicate, invites, mass mention; actions delete/warn/timeout | No multi-threshold violation ladder comparable to competitor “basic/advanced” docs |
| Moderation | `apps/bot/bot/moderation.py` — kick/ban/timeout/purge/userinfo; `mod_warn` in log map; Redis modlog via `apps/api/app/routes/moderation.py` | Warn-centric history UX/depth is a discovery gap vs competitor modlog+warnings |

---

## 4. YAGPDB feature inventory

Summarized from public sources (capability names only; no branding or prose reuse). Limits cited are free → premium where docs state them.

### 4.1 Notifications and feeds

| Capability | Public notes | Primary source |
| --- | --- | --- |
| Notifications hub | Reddit, RSS, Streaming (Discord presence), Twitch, YouTube | [Notifications](https://help.yagpdb.xyz/docs/notifications/) |
| RSS | Feed URL → channel; optional role/@everyone; poll latency up to ~5 minutes; **2 free / 10 premium** active feeds | [RSS](https://help.yagpdb.xyz/docs/notifications/rss/) |
| YouTube | Channel subscribe; livestreams/shorts toggles; mentions; custom announcement templates; **10 / 250** | [YouTube](https://help.yagpdb.xyz/docs/notifications/youtube/) |
| Twitch | Channel name; live + optional VOD; mentions; custom announcement (premium); **3 / 15** | [Twitch](https://help.yagpdb.xyz/docs/notifications/twitch/) |
| Reddit | Subreddit name; embed vs plain; premium feed limits on site | [Reddit](https://help.yagpdb.xyz/docs/notifications/reddit/) |
| Streaming (Discord) | Announce / streaming role from Discord streaming status; game/title regex | [Streaming](https://help.yagpdb.xyz/docs/notifications/streaming/) |
| General | Join/leave channel messages; join DM; topic-change message | [General](https://help.yagpdb.xyz/docs/notifications/general/) |

Homepage also positions Reddit/YouTube/Twitch/RSS as “fast” feeds (minutes-scale).

### 4.2 Custom commands

| Capability | Public notes | Primary source |
| --- | --- | --- |
| Template CCs | Triggers (starts with, contains, exact, regex); dynamic responses; groups; channel/role restrictions; interval/cron and other trigger types documented in help | [Custom commands](https://help.yagpdb.xyz/docs/custom-commands/), [Commands](https://help.yagpdb.xyz/docs/custom-commands/commands/) |
| Context-menu CCs | User and Message Apps context-menu triggers; free **1 of each type**, premium **5**; `.Author` / `.TargetUser` / `.TargetMember` semantics | [v2.82.0](https://github.com/botlabs-gg/yagpdb/releases/tag/v2.82.0) (2026-06-29), PR #2079 |
| Premium CC limits | e.g. CC count 100→500, slash CCs 3→10, template ops, DB rows (premium page) | [yagpdb.xyz](https://yagpdb.xyz/) / premium perks |

### 4.3 Moderation, roles, utilities (homepage / help / commands index)

- Automoderator (basic + advanced): violation thresholds, mute/kick/ban ladders, banned words/websites, Safe Browsing-style options (help).
- Self-assignable roles / role menus: groups, reaction menus, single vs multiple modes, require/ignore roles.
- General moderation: kick/ban/clean, timed mutes/bans, warnings, modlog, message logs.
- Reminders (`remindme` / reminders), soundboard, reputation, tickets (incl. premium threaded tickets), fun commands including Cat Fact.
- Open-source self-host positioning on homepage and GitHub.

### 4.4 Positioning vs NorBot

YAGPDB optimizes for **server-operator scripting + feed breadth**. NorBot optimizes for **operator dashboard + security/community workflows + campaigns + curated trending**, with content notifications as a platform-adapter subsystem rather than a free-form feed dump.

---

## 5. Feature-gap matrix

Columns: YAGPDB capability · Primary source URL · NorBot status · Repository evidence · User value · Strategic fit · Differentiation potential · Technical dependencies · Security/abuse risk · Operational cost · Complexity · Recommended priority · MVP boundary · Acceptance signal

Statuses: **Present** · **Partial** · **Absent** · **N/A (NorBot-specific)**.

| YAGPDB capability | Primary source URL | NorBot status | Repository evidence | User value | Strategic fit | Differentiation potential | Technical dependencies | Security/abuse risk | Operational cost | Complexity | Recommended priority | MVP boundary | Acceptance signal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Standalone RSS feeds (URL → Discord channel; ~5 min poll; 2/10 caps) | https://help.yagpdb.xyz/docs/notifications/rss/ | Absent | No RSS in content platform registry; Top Trending is `feed_channels`, not RSS | High for news/blog servers | High if scoped and rate-limited | Medium — compete on reliability + dashboard UX, not limit games | New poller or CN worker extension; fetch allowlist; storage; Discord post path | SSRF, malicious feed, spam floods | Medium–high (egress + poll fan-out) | Medium | **Now** (feasibility first) | Feasibility doc + threat model before build; hard guild/global caps | Feasibility doc merged; go/no-go recorded |
| Rich Link Embeds / link embed repair | https://yagpdb.xyz/ (general utility expectation; not a dedicated help page cited) | Absent as product module | Embed Library + EmbedSync exist; no “repair Discord link embeds” feature in sidebar | High for media/community channels | High — complements campaigns & embeds | High if quality > Discord defaults | Bot message pipeline; unfurl/oEmbed providers; cache | SSRF, NSFW, tracking redirects, rate abuse | Medium | Medium | **Now** | Safe provider allowlist; per-guild toggle; no arbitrary HTML render | Operators can fix/enrich a broken link post with measurable success rate |
| YouTube creator notifications | https://help.yagpdb.xyz/docs/notifications/youtube/ | Present | YouTube adapter + CN routes/worker | High | Already core | Medium — templates/shorts/live parity optional | Existing CN | API quota abuse | Medium | Low–med | Next (parity polish only) | Stay on adapter path; no CC template language | Existing subscribe + post flow remains healthy |
| Twitch live notifications | https://help.yagpdb.xyz/docs/notifications/twitch/ | Present | Twitch adapter + CN | High | Already core | Medium — VOD/custom message optional | Existing CN | API quota | Medium | Low–med | Next (parity polish only) | Live announce MVP already; VOD optional later | Live events post reliably |
| Reddit subreddit feeds | https://help.yagpdb.xyz/docs/notifications/reddit/ | Absent | Not in `PlatformLiteral` / registry | Medium–high | High via CN extension | Medium | New Reddit adapter; auth/ToS; polling | Ban evasion, NSFW, spam subs | Medium | Medium | **Next** | Read-only official API path; NSFW policy; per-guild caps | Subreddit → channel posts with audit trail |
| Discord “streaming status” announce/role | https://help.yagpdb.xyz/docs/notifications/streaming/ | Absent | No streaming-presence cog | Low–medium | Low–medium | Low | Presence intents; role churn | Role griefing | Low–medium | Low–medium | Later / Reject lean | Only if customers ask | — |
| Join/leave + join DM | https://help.yagpdb.xyz/docs/notifications/general/ | Present / Partial | Welcome & Leave automation; verification may own join UX | High | Present | Low | Existing automation | DM spam | Low | Low | — | Keep NorBot join/verification story | — |
| Arbitrary custom command templating | https://help.yagpdb.xyz/docs/custom-commands/ | Absent (by design) | Autoresponses are keyword + light tokens only | High for power users | Poor (ops/security) | Negative if insecure | Sandbox VM, quotas, DB | **Critical** DoS, data exfil, abuse | Very high | Very high | **Reject** | Do not ship template language | Explicit product decision: autoresponses only |
| Context-menu custom commands (v2.82.0) | https://github.com/botlabs-gg/yagpdb/releases/tag/v2.82.0 | Absent | No CC engine | Medium | Poor without CC platform | Low | Same as CC | High | High | High | **Reject** (with CC) | — | — |
| Keyword auto-responses | Custom commands / autoresponder-class | Present | `autoresponder.py`, autoresponder API, Automation sidebar | Medium–high | Strong | Medium (simplicity) | Existing | Prompt injection light | Low | Low | — | Keep simple substitution | — |
| Automod (thresholds, websites, Safe Browsing, advanced rulesets) | https://help.yagpdb.xyz/docs/moderation/basic-automoderator/ | Partial | `automod.py` route + bot cog: words/spam/dup/invites/mentions | High | High | Medium via NorBot security suite | Rules engine discovery | False positives | Medium | Medium–high | **Next** (discovery) | Inventory competitor rules vs NorBot; ship only high-ROI deltas | Gap list with prioritized rules |
| Warnings + deep mod history | https://yagpdb.xyz/ (moderation positioning) | Partial | Redis modlog list API; `mod_warn` mapped but no first-class `/warn` command in `moderation.py` | High for mod teams | High | Medium | Persist warn records; dashboard UI | Privacy retention | Low–medium | Medium | **Next** | Durable warn entities + lookup by user | Mods can warn and retrieve history |
| Role menus (advanced group modes) | https://help.yagpdb.xyz/docs/roles/self-assignable-roles/ | Partial | `roles.py` give/take/toggle; role menus API | Medium–high | Medium | Low–medium | Menu schema + UI | Role escalation | Low | Medium | **Later** | Exclusive groups / require-role after core polish | Configurable exclusivity without scripts |
| Reminders | https://help.yagpdb.xyz/docs/core/all-commands/ | Absent | No reminder worker/cog | Medium | Medium | Low | Scheduler + durable jobs | Spam DMs | Medium | Medium | **Later** | Per-user caps; no CC | User receives reminder once |
| Polls | (commonly via CC / utilities) | Absent as product | No poll module | Medium | Medium | Medium if native Discord polls used well | Discord poll APIs or components | Vote stuffing | Low–medium | Low–medium | **Later** | Prefer native Discord polls wrapper | Staff can open poll from dashboard or slash |
| Soundboard / Cat Facts / dadjoke-class | https://help.yagpdb.xyz/docs/fun/soundboard/ ; getting-started CatFact | Absent | — | Low | Poor | None | Voice infra / fluff | Noise, ToS | Medium (voice) | Varies | **Reject** | — | — |
| Tickets | Homepage / premium threaded tickets | Present | Tickets cog + API + Community sidebar | High | Present | Medium (NorBot UX) | Existing | Abuse channels | Medium | — | — | — | — |
| Campaigns / bulk messaging | N/A (NorBot strength) | Present (NorBot) | Campaigns routes/worker/dashboard | High | Core | **High** | Existing | Spam compliance | Medium | — | Defend | — | — |
| Top Trending feed channels | N/A (NorBot) | Present (NorBot) | feed_channels* | High | Core | **High** vs RSS | Existing | Vote gaming | Medium | — | Defend | Do not rebrand as RSS | — |
| Verification / honeypot / raid | N/A (NorBot) | Present (NorBot) | verification*, honeypot*, raid* | High | Core | **High** | Existing | — | — | — | Defend | — | — |
| AGPL copy of any YAGPDB code/design | GitHub botlabs-gg/yagpdb | Policy Reject | — | — | — | — | — | License risk | — | — | **Reject** | Clean-room only | Legal review if unsure |

---

## 6. Recommended additions

### 6.1 Now

1. **RSS feasibility (separate document)**  
   Treat as an engineering/product spike: polling model (~5 minute class latency is acceptable), allowlisted schemes/hosts, SSRF controls, per-guild and global caps (competitor free/premium envelope is a *reference*, not a target), interaction with existing `content_notification_worker` vs a dedicated feed worker, and Discord posting/templates using NorBot embed library—not competitor template syntax.

2. **Rich Link Embeds**  
   Productize repair/enrichment of link previews where Discord fails or operators want brand-consistent cards. Fit beside Embed Library and EmbedSync. Prefer allowlisted unfurl providers and explicit opt-in per guild.

### 6.2 Next

1. **Reddit via Content Notifications** — add a first-class platform adapter under `apps/api/app/integrations/content_platforms/` with the same availability/circuit/throttle patterns as YouTube/Twitch.  
2. **Automod parity discovery** — structured comparison of competitor basic/advanced rules against `AutomodConfig`; ship only rules that close real incident gaps.  
3. **Warnings / mod-history depth** — promote warns from “log action name” to durable, queryable history aligned with Discord Logs / Audit Logs UX.

### 6.3 Later (if demand persists)

- Polls (prefer Discord-native).  
- Reminders with hard caps.  
- Advanced role-menu modes (exclusive groups, require/ignore role) without a scripting language.

---

## 7. Rejected or deferred features

| Item | Decision | Rationale |
| --- | --- | --- |
| Arbitrary custom-command templating / context-menu CCs | **Reject** | Sandbox, multi-tenant DoS, data-access, and support burden dominate value; autoresponses already cover common FAQ needs |
| Cat Facts / novelty fun commands | **Reject** | Brand dilution; no strategic fit |
| Soundboard | **Defer / lean Reject** | Voice ops cost and abuse without clear NorBot positioning |
| Discord streaming-status roles | **Defer** | Overlaps weakly with Twitch/Kick CN; presence complexity |
| AGPL copy of competitor code, templates, or distinctive UX prose | **Reject** | License and IP risk; clean-room only |
| Rebranding Top Trending as “RSS” | **Reject** | Different product; confuses operators |

---

## 8. Suggested product phases

### Phase A — Now (foundation)

- RSS feasibility + security/cost model (doc only until go).  
- Rich Link Embeds MVP (allowlist, guild toggle, repair/enrich flow).  
- Defend existing CN (YouTube/Twitch) reliability and worker health visibility.

### Phase B — Next (feed + moderation depth)

- Reddit adapter in content notifications.  
- Automod discovery → thin rule additions.  
- Warnings + mod history depth in bot + API + dashboard.

### Phase C — Later (convenience)

- Polls, reminders, advanced role-menu modes.  
- Optional CN polish (Twitch VOD, YouTube shorts/live toggles) if customers ask—without importing a template language.

### Phase D — Explicit non-goals

- Custom command platform; novelty fun pack; AGPL-derived implementations.

---

## 9. Engineering implications

1. **Reuse the content platform abstraction** for Reddit and (if approved) RSS-as-adapter or parallel feed worker—do not invent a third notification stack. Evidence: `registry.py`, `content_notification_worker.py`, `content_notifications.py`.  
2. **Keep Top Trending separate** (`feed_channels` ranking/votes/repair). RSS must not overload those tables or the FeedChannelsCog.  
3. **Rich Link Embeds** likely touch bot message handling and possibly `embed_render` / EmbedSync; keep provider fetch on the API or a sandboxed worker, not unbounded bot-side HTTP.  
4. **Autoresponses stay dumb-on-purpose** — expanding `{token}` substitution carefully is fine; evaluating templates is not.  
5. **Moderation depth** needs durable storage beyond Redis list UX if history is a product promise (`moderation.py` Redis `lrange` today).  
6. **No AGPL contamination** — clean-room specs from public behavior only; do not vendor competitor modules.

---

## 10. Security and abuse considerations

| Risk | Applies to | Mitigation direction |
| --- | --- | --- |
| SSRF / internal network probe | RSS, Rich Link Embeds, unfurl | Block private IPs/metadata endpoints; DNS rebinding controls; scheme allowlist |
| Feed / unfurl spam | RSS, Reddit, embeds | Per-guild caps; backoff; circuit breakers (CN already opens circuits) |
| NSFW / illegal content relay | Reddit, RSS, embeds | Policy filters; guild NSFW channel gates; blocklists |
| Automod false positives / evasion | Automod expansion | Gradual rollout; exempt roles; audit logs |
| Custom command DoS / secret leak | Rejected CC platform | Do not build |
| Moderation data retention | Warn history | Retention policy; manager-only access (existing guild manager deps) |
| Kick/X credential exposure | Gated platforms | Secrets in env only; availability reasons already surface missing creds |

TikTok remains **blocked** pending an approved creator-OAuth path (`tiktok/adapter.py`)—treat as compliance boundary, not a gap to close casually.

---

## 11. Operational and cost implications

| Area | Cost drivers | Notes |
| --- | --- | --- |
| RSS | Egress bandwidth, poll frequency × feeds × guilds, HTML/XML parse CPU | Competitor ~5 minute poll and 2/10 caps illustrate why uncapped free RSS is expensive |
| Reddit | API rate limits / auth tiers | Prefer official API; cache aggressively |
| YouTube/Twitch (existing) | Quota + webhook lease renewal | Worker already manages cursors/subscriptions |
| Kick/X | Credentialed APIs; X poll default | Keep gated until credentials and budget exist |
| Rich Link Embeds | Provider rate limits + cache storage | Cache by URL hash; TTL |
| Automod / warns | Redis/Postgres volume; support load | Prefer Postgres if history is durable product |
| Custom commands (rejected) | Would dominate support and compute | Avoided cost is intentional |

Worker Health (`/observability/worker-health`) should remain the operator lens for any new poller.

---

## 12. Open questions

1. Should RSS be a **new platform type** under content notifications, or a **separate feed product** with its own caps UI?  
2. What is the minimum Rich Link Embeds MVP: repair-only, enrich-on-post, or staff slash command?  
3. Reddit: which API product tier and NSFW policy for multi-tenant SaaS?  
4. For warnings: Redis retention vs Postgres-backed case history?  
5. Automod: prioritize website/phishing checks vs violation-threshold ladders first?  
6. Do enterprise customers demand Discord streaming-status roles enough to justify presence intent?  
7. Legal: confirm clean-room process and license review cadence when referencing AGPL competitors.  
8. Premium: will NorBot ever sell feed-limit tiers, or keep flat fair-use caps?

---

## 13. Source bibliography

### Competitor primary sources

| Source | URL | Used for |
| --- | --- | --- |
| Homepage / product positioning | https://yagpdb.xyz/ | Feeds, moderation, roles, CC overview, open-source note |
| Notifications index | https://help.yagpdb.xyz/docs/notifications/ | Feed surface map |
| RSS | https://help.yagpdb.xyz/docs/notifications/rss/ | 2 free / 10 premium; ~5 minute poll; channel/role mention |
| YouTube | https://help.yagpdb.xyz/docs/notifications/youtube/ | Limits, livestreams/shorts, announcement templates |
| Twitch | https://help.yagpdb.xyz/docs/notifications/twitch/ | Limits, VOD, premium custom announcement |
| Reddit | https://help.yagpdb.xyz/docs/notifications/reddit/ | Subreddit → channel; embed toggle |
| Streaming | https://help.yagpdb.xyz/docs/notifications/streaming/ | Discord streaming status announce/role |
| General notifications | https://help.yagpdb.xyz/docs/notifications/general/ | Join/leave/DM/topic |
| Custom commands hub | https://help.yagpdb.xyz/docs/custom-commands/ | CC product area |
| Custom commands detail | https://help.yagpdb.xyz/docs/custom-commands/commands/ | Triggers, groups, context-menu limits |
| Release v2.82.0 | https://github.com/botlabs-gg/yagpdb/releases/tag/v2.82.0 | Context-menu CCs (2026-06-29) |
| Getting started | https://help.yagpdb.xyz/docs/welcome/getting-started/ | CatFact-class novelty positioning |
| Basic automoderator | https://help.yagpdb.xyz/docs/moderation/basic-automoderator/ | Threshold/rules inventory reference |
| Self-assignable roles | https://help.yagpdb.xyz/docs/roles/self-assignable-roles/ | Advanced role menu modes |
| Soundboard | https://help.yagpdb.xyz/docs/fun/soundboard/ | Fun/voice feature (reject lean) |
| All commands index | https://help.yagpdb.xyz/docs/core/all-commands/ | Reminders and command breadth |

### NorBot repository evidence (selected)

| Path | Evidence |
| --- | --- |
| `apps/dashboard/src/components/navigation/sidebar.tsx` | `SIDEBAR_GROUPS` product map |
| `apps/api/app/main.py` | Router registration |
| `apps/bot/bot/client.py` | Cog inventory |
| `apps/api/app/workers/content_notification_worker.py` | CN worker |
| `apps/api/app/workers/campaign_worker.py` | Campaign worker |
| `apps/api/app/routes/content_notifications.py` | Platform literals |
| `apps/api/app/integrations/content_platforms/registry.py` | Adapter registry + availability |
| `apps/api/app/integrations/content_platforms/tiktok/adapter.py` | TikTok blocked |
| `apps/api/app/integrations/content_platforms/kick/adapter.py` | Kick credential gate |
| `apps/api/app/integrations/content_platforms/x/adapter.py` | X credential gate |
| `apps/api/app/routes/feed_channels.py` / `apps/bot/bot/feed_channels.py` | Top Trending (not RSS) |
| `apps/bot/bot/autoresponder.py` | Keyword autoresponses |
| `apps/bot/bot/roles.py` | Role menu modes |
| `apps/api/app/routes/automod.py` | Automod config surface |
| `apps/bot/bot/moderation.py` / `apps/api/app/routes/moderation.py` | Moderation actions + Redis modlog |

---

*Document owner: NorBot product/engineering. Update when RSS feasibility concludes or when CN platform set changes.*
