# Manual Discord Integration Test Matrix

This matrix validates the logging configuration architecture and the embed
message publishing flow against a real (dummy) Discord server. Run it after any
change to the logging provisioning, routing, repair, or embed publish paths.

## Prerequisites

- A dummy Discord guild where you have **Manage Server** and **Administrator**.
- The Norgoth bot invited to that guild.
- `DISCORD_BOT_TOKEN` configured for the API; API, bot, Postgres, and Redis running.
- The bot role positioned **above** any category/channels it must manage.

### Required bot permissions

| Capability | Discord permission | Used by |
| --- | --- | --- |
| Create/delete categories & channels | Manage Channels | Provision, Repair, Reset |
| Read channels | View Channels | Reconcile / health |
| Post log embeds & embed messages | Send Messages, Embed Links | Routing, Publish |
| Delete posted messages | Manage Messages | Embed delete (Discord), Purge |
| Ban/unban logging | Moderation (Ban Members) + `moderation` intent | Member ban/unban events |
| Message edit/delete logging | Message Content intent | Message events |

## A. Logging setup wizard + provisioning

| # | Step | Expected |
| --- | --- | --- |
| A1 | Open **Logging → Logging Configurations** with no config | Wizard (STATE A) is shown, event catalog loads |
| A2 | Step 1: enable managed category, name it, pick an emoji | Name + emoji accepted |
| A3 | Step 2: include Members + Messages groups, "New channel" | Sanitized names shown (lowercase, hyphenated) |
| A4 | Step 2: set one group to "Existing" without picking | Next is blocked with a validation message |
| A5 | Step 3: change a group color; enable "Custom color" on one event | Color pickers update; per-event override recorded |
| A6 | Step 4 review → **Create logging** | Category + channels created in Discord; config becomes **Active** |
| A7 | Inspect Discord | New category contains the new log channels under Norgoth's category |
| A8 | Inspect DB | `logging_configurations`, `logging_channels`, `logging_event_mappings` populated; `status = active` |
| A9 | Inspect Redis | `norgoth:guild:{id}:logging:routing` snapshot present with `enabled: true` and event→channel/color map |

## B. Runtime event routing

For each event, perform the action in Discord and confirm a standardized embed
posts to the mapped channel with the configured color.

| # | Action | Event type | Expected channel | Color |
| --- | --- | --- | --- | --- |
| B1 | A member joins | `member_join` | Members group channel | group/override |
| B2 | A member leaves | `member_leave` | Members | group |
| B3 | Ban then unban a user | `member_ban`, `member_unban` | Members | group |
| B4 | Timeout a member | `member_timeout` | Members | group |
| B5 | Edit a message | `message_edit` | Messages | group |
| B6 | Delete a message | `message_delete` | Messages | group |
| B7 | Bulk delete (purge) | `message_bulk_delete` | Messages | group |
| B8 | Create/delete/rename a role | `role_*` | Roles (if mapped) | group |
| B9 | Create/delete/update a channel | `channel_*` | Channels (if mapped) | group |
| B10 | Change server name | `guild_update` | Server (if mapped) | group |
| B11 | Join/leave/move voice | `voice_*` | Voice (if mapped) | group |
| B12 | Run `/kick`, `/ban`, `/timeout`, `/purge` | `mod_*` | Moderation (if mapped) | moderation |
| B13 | Disable "Logging enabled" toggle | — | No new embeds route; audit timeline still records events |

## C. Reconcile / repair / reset

| # | Step | Expected |
| --- | --- | --- |
| C1 | **Check health** with everything intact | All channels `ok`; category `ok` |
| C2 | Manually delete a Norgoth-managed log channel in Discord, **Check health** | That channel shows `missing` |
| C3 | **Repair missing** | Missing managed channel is recreated; snapshot refreshed |
| C4 | Delete the managed category, **Repair missing** | Category + managed channels recreated |
| C5 | Point a group at an **existing** channel, delete that channel, **Check health** | Shows `missing`; Repair does **not** recreate (not managed) |
| C6 | **Reset** without "delete Discord" | Config removed; Discord channels remain; snapshot cleared; wizard returns |
| C7 | Re-create config, **Reset** with "delete Discord" checked | Managed channels + category deleted in Discord |

## D. Reconfigure

| # | Step | Expected |
| --- | --- | --- |
| D1 | With a config present, click **Reconfigure** | Wizard opens pre-seeded from catalog; Cancel returns to summary |
| D2 | Complete the wizard again | Config fully replaced (channels/events); snapshot rewritten |

## E. Legacy migration (on-read import)

| # | Step | Expected |
| --- | --- | --- |
| E1 | Seed legacy Redis `…:logging` with a default log channel + category channels, and automation `mod_log_channel_id` | — |
| E2 | Open **Logging Configurations** (no Postgres config yet) | A config is imported: groups mapped to existing channels, moderation mapped to the mod log channel, `status = active` |
| E3 | Trigger events from section B | Routed to the imported channels; nothing was provisioned/created |

## F. Audit Logs consolidation

| # | Step | Expected |
| --- | --- | --- |
| F1 | Open **Logging → Audit Logs** | Moderation actions and server events appear in one timeline, newest first |
| F2 | Toggle Source filter (All / Moderation / Server Events) | Rows filter accordingly |
| F3 | Use search + date range | Rows filter by text and time |
| F4 | Expand a row | Shows details/fields for that event |

## G. Embed messages: publish / edit / re-sync / delete

| # | Step | Expected |
| --- | --- | --- |
| G1 | Create an embed message, choose ≥1 target channel, Save | Targets stored; nothing posted yet |
| G2 | From the master table, **Publish** | Message posted to each target; row shows synced/sent count |
| G3 | Edit the embed content, Save, then **Re-Sync** | Previously posted messages are edited in place |
| G4 | **Publish** disabled with no targets | Button disabled until a target is chosen |
| G5 | Delete template without "delete Discord" | Template removed; posted messages remain |
| G6 | Delete template with "Also delete… Discord" checked | Template removed and posted messages deleted |

## Notes

- Discord rate limits (HTTP 429) are retried automatically by the API's bot REST
  client; provisioning many channels at once should still succeed.
- If provisioning partially fails, the config remains and the failed channels are
  reported; re-run **Provision**/**Repair** to finish.
