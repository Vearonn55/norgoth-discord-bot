# NorBot Discord commands

Generated from the bot command registry (`COMMAND_MANIFEST_VERSION=2026-09-03.1`).

Do not edit by hand — run:

```bash
python Norgoth/apps/bot/scripts/export_command_docs.py
```

## General

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/help` | List NorBot commands available to you. | `—` | ephemeral |
| `/dashboard` | Open the NorBot dashboard for this server. | `—` | ephemeral |
| `/status` | Show bot health for this server. | `—` | ephemeral |

## Info

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/userinfo` | Show info about a member. | `—` | ephemeral |
| `/avatar` | Show a user's avatar. | `—` | public |
| `/server` | Show information about this server. | `—` | public |
| `/roles` | List roles in this server. | `—` | ephemeral |

## Levels

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/rank` | Show your (or a member's) level and XP. | `leveling` | public |
| `/give-xp` | Grant XP to a member (Manage Server required). | `leveling` | public |
| `/leaderboard` | Show the server XP leaderboard. | `leveling` | public |
| `/level-reset` | Reset a member's XP (text, voice, or all). | `leveling` | ephemeral |

## Moderation

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/kick` | Kick a member from the server. | `moderation` | ephemeral |
| `/ban` | Ban a user from the server. | `moderation` | ephemeral |
| `/timeout` | Timeout a member for a number of minutes. | `moderation` | ephemeral |
| `/purge` | Delete the last N messages in this channel. | `moderation` | ephemeral |
| `/role add` | Give a role to a member. | `roles` | ephemeral |
| `/role remove` | Remove a role from a member. | `roles` | ephemeral |
| `/unban` | Remove a ban from a user. | `moderation` | ephemeral |
| `/untimeout` | Remove a timeout from a member. | `moderation` | ephemeral |
| `/setnick` | Set or clear a member's nickname. | `moderation` | ephemeral |
| `/vkick` | Disconnect a member from voice. | `moderation` | ephemeral |
| `/move` | Move a member to a voice channel. | `moderation` | ephemeral |
| `/lock` | Lock a text channel (deny @everyone Send Messages). | `moderation` | ephemeral |
| `/unlock` | Unlock a text channel. | `moderation` | ephemeral |
| `/slowmode` | Set slowmode for a text channel. | `moderation` | ephemeral |
| `/modlogs` | Show recent moderation actions for this server. | `moderation` | ephemeral |

## Tickets

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/ticket close` | Close this ticket. | `tickets` | channel |
| `/ticket add` | Add a member to this ticket channel. | `tickets` | ephemeral |
| `/ticket remove` | Remove a member from this ticket channel. | `tickets` | ephemeral |

## Invites

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/invites` | Show how many members someone has invited. | `invites` | public |
| `/invites-top` | Show the invite leaderboard. | `invites` | public |

## Verification

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/verification pending` | Show pending manual verifications (dashboard link). | `—` | ephemeral |

## Campaigns

| Command | Description | Module | Visibility |
|---|---|---|---|
| `/unsubscribe` | Stop receiving campaign DMs from this server. | `campaigns` | ephemeral |

## Context menus (user)

| Name | Description | Module |
|---|---|---|
| Kick | Kick this member. | `moderation` |
| Ban | Ban this user. | `moderation` |
| Timeout | Timeout this member for 10 minutes. | `moderation` |
| User info | Show info about this member. | `—` |

