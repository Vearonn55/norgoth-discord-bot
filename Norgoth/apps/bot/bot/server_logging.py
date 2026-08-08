"""Server event logging: member, message, role, and channel events.

Each event is appended to a Redis ring buffer (norgoth:guild:{id}:eventlog)
for the dashboard and, when a log channel is configured, posted as an embed.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

import discord
from discord.ext import commands

from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.serverlog")

EVENT_LOG_CAP = 1000

CATEGORY_COLORS = {
    "member": discord.Color.green(),
    "message": discord.Color.blurple(),
    "role": discord.Color.gold(),
    "channel": discord.Color.teal(),
    "server": discord.Color.purple(),
    "voice": discord.Color.teal(),
    "thread": discord.Color.dark_teal(),
    "moderation": discord.Color.red(),
    "security": discord.Color.dark_red(),
}

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "log_channel_id": None,
    "member_events": True,
    "message_events": True,
    "role_events": True,
    "channel_events": True,
    "member_channel_id": None,
    "message_channel_id": None,
    "role_channel_id": None,
    "channel_channel_id": None,
    "groups": [],
}


def logging_config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:logging"


def routing_snapshot_key(guild_id: int | str) -> str:
    """Postgres-backed, denormalised routing map written by the API."""

    return f"norgoth:guild:{guild_id}:logging:routing"


def event_log_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:eventlog"


def build_log_embed(
    title: str,
    description: str,
    *,
    color: discord.Color,
    fields: dict[str, str] | None = None,
    footer: str | None = None,
) -> discord.Embed:
    """Standardised log embed used for every routed logging event."""

    embed = discord.Embed(
        title=title[:256],
        description=description[:4000],
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    if footer:
        embed.set_footer(text=footer[:2048])
    for key, value in list((fields or {}).items())[:20]:
        embed.add_field(name=str(key)[:256], value=str(value)[:1024], inline=True)
    return embed


class ServerLoggingCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        stored = await self.bot.state.get_json(logging_config_key(guild_id))
        return {**DEFAULT_CONFIG, **stored}

    async def get_routing_snapshot(self, guild_id: int) -> dict[str, Any] | None:
        """Read the API-managed routing snapshot, if one exists and is active."""

        snapshot = await self.bot.state.get_json(routing_snapshot_key(guild_id))
        if snapshot and snapshot.get("enabled") and snapshot.get("events"):
            return snapshot
        return None

    async def route_event(
        self,
        guild: discord.Guild,
        event_type: str,
        category: str,
        title: str,
        description: str,
        fields: dict[str, str],
        *,
        actor_name: str | None = None,
    ) -> bool:
        """Send a standardised embed to the channel/colour resolved for an event.

        Prefers the API-managed routing snapshot (event_type -> channel + colour).
        Falls back to the legacy Redis logging config when no snapshot matches.
        Returns True when the event was routed to at least one channel.
        """

        channel_ids: set[str] = set()
        color: discord.Color = CATEGORY_COLORS.get(
            category, discord.Color.dark_grey()
        )

        snapshot = await self.get_routing_snapshot(guild.id)
        routed = snapshot["events"].get(event_type) if snapshot else None
        if routed and routed.get("channel_id"):
            channel_ids.add(str(routed["channel_id"]))
            if routed.get("color") is not None:
                try:
                    color = discord.Color(int(routed["color"]))
                except (ValueError, TypeError):
                    pass
        else:
            channel_ids = self._legacy_channel_ids(
                await self.get_config(guild.id), category, event_type
            )

        if not channel_ids:
            return False

        footer = f"Norgoth · {category} event"
        if actor_name:
            footer = f"{footer} · by {actor_name}"
        embed = build_log_embed(
            title, description, color=color, fields=fields, footer=footer
        )

        sent = False
        for channel_id in channel_ids:
            channel = guild.get_channel(int(channel_id))
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                await channel.send(embed=embed)
                sent = True
            except discord.HTTPException:
                logger.exception(
                    "Failed to post log embed to channel %s", channel_id
                )
        return sent

    def _legacy_channel_ids(
        self,
        config: dict[str, Any],
        category: str,
        event_type: str,
    ) -> set[str]:
        """Resolve target channels from the legacy Redis config."""

        if not config.get("enabled", True):
            return set()
        if not config.get(f"{category}_events", True):
            return set()

        channel_ids: set[str] = set()
        for group in config.get("groups") or []:
            if not isinstance(group, dict) or not group.get("enabled", True):
                continue
            keys = group.get("event_keys") or []
            if event_type in keys:
                gid = group.get("channel_id")
                if gid:
                    channel_ids.add(str(gid))

        fallback = config.get(f"{category}_channel_id") or config.get(
            "log_channel_id"
        )
        if fallback and not channel_ids:
            channel_ids.add(str(fallback))
        return channel_ids

    async def log_moderation(
        self,
        guild: discord.Guild,
        event_type: str,
        title: str,
        description: str,
        fields: dict[str, str],
        *,
        actor_name: str | None = None,
    ) -> None:
        """Route a moderation action through config-driven logging.

        Moderation actions keep their own audit trail (moderation log); this only
        mirrors them into a configured logging channel when routing is set up.
        """

        if not await self.bot.state.is_module_enabled(guild.id, "logging"):
            return
        try:
            await self.route_event(
                guild,
                event_type,
                "moderation",
                title,
                description,
                fields,
                actor_name=actor_name,
            )
        except Exception:  # noqa: BLE001 - logging must never break moderation
            logger.exception("Failed to route moderation log event")

    async def resolve_audit_actor(
        self,
        guild: discord.Guild,
        action: discord.AuditLogAction,
        *,
        target_id: int | None = None,
    ) -> tuple[str | None, str | None]:
        """Best-effort actor lookup from Discord's audit log."""

        try:
            async for entry in guild.audit_logs(limit=6, action=action):
                if target_id is not None and entry.target is not None:
                    if getattr(entry.target, "id", None) != target_id:
                        continue
                user = entry.user
                if user is None:
                    return None, None
                return str(user.id), str(user)
        except (discord.Forbidden, discord.HTTPException):
            return None, None

        return None, None

    async def record_event(
        self,
        guild: discord.Guild,
        category: str,
        action: str,
        description: str,
        fields: dict[str, str] | None = None,
        *,
        event_type: str,
        actor_id: str | None = None,
        actor_name: str | None = None,
    ) -> None:
        if not await self.bot.state.is_module_enabled(guild.id, "logging"):
            return

        entry_fields = dict(fields or {})
        if actor_name and "Actor" not in entry_fields:
            entry_fields["Actor"] = actor_name
        if actor_id and "Actor ID" not in entry_fields:
            entry_fields["Actor ID"] = actor_id

        # Always capture the event in the ring buffer that powers the dashboard
        # Audit Logs, independent of whether it is routed to a Discord channel.
        entry = {
            "id": str(uuid.uuid4()),
            "category": category,
            "action": action,
            "description": description,
            "fields": entry_fields,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "event_type": event_type,
            "created_at": now_iso(),
        }

        try:
            await self.bot.state.append_capped_list(
                event_log_key(guild.id),
                entry,
                cap=EVENT_LOG_CAP,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to append event log entry")

        try:
            await self.route_event(
                guild,
                event_type,
                category,
                action,
                description,
                entry_fields,
                actor_name=actor_name,
            )
        except Exception:  # noqa: BLE001 - routing must not break event capture
            logger.exception("Failed to route log event %s", event_type)

    # ---- member events -------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await self.record_event(
            member.guild,
            "member",
            "Member joined",
            f"{member.display_name} ({member}) joined the server.",
            {
                "Member": f"{member} ({member.id})",
                "Account created": member.created_at.strftime("%Y-%m-%d"),
                "Member count": str(member.guild.member_count),
            },
            event_type="member_join",
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        roles = [role.name for role in member.roles if not role.is_default()]
        actor_id, actor_name = await self.resolve_audit_actor(
            member.guild,
            discord.AuditLogAction.kick,
            target_id=member.id,
        )

        description = f"{member} ({member.id}) left the server."
        if actor_name:
            description = (
                f"{member} ({member.id}) was removed from the server "
                f"(likely kicked by {actor_name})."
            )

        await self.record_event(
            member.guild,
            "member",
            "Member left",
            description,
            {
                "Member": f"{member} ({member.id})",
                "Roles": ", ".join(roles) if roles else "None",
                "Member count": str(member.guild.member_count),
            },
            event_type="member_leave",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        before_timeout = getattr(before, "timed_out_until", None)
        after_timeout = getattr(after, "timed_out_until", None)
        if before_timeout != after_timeout and after_timeout is not None:
            actor_id, actor_name = await self.resolve_audit_actor(
                after.guild,
                discord.AuditLogAction.member_update,
                target_id=after.id,
            )
            await self.record_event(
                after.guild,
                "member",
                "Member timed out",
                f"{after.display_name} was timed out.",
                {
                    "Member": f"{after} ({after.id})",
                    "Until": after_timeout.strftime("%Y-%m-%d %H:%M UTC"),
                },
                event_type="member_timeout",
                actor_id=actor_id,
                actor_name=actor_name,
            )

        if before.nick != after.nick:
            actor_id, actor_name = await self.resolve_audit_actor(
                after.guild,
                discord.AuditLogAction.member_update,
                target_id=after.id,
            )
            await self.record_event(
                after.guild,
                "member",
                "Nickname changed",
                (
                    f"{after.display_name}'s nickname changed from "
                    f"“{before.nick or before.name}” to "
                    f"“{after.nick or after.name}”."
                ),
                {
                    "Member": f"{after} ({after.id})",
                    "Before": before.nick or before.name,
                    "After": after.nick or after.name,
                },
                event_type="member_nickname",
                actor_id=actor_id,
                actor_name=actor_name,
            )

        if before.roles != after.roles:
            gained = [r for r in after.roles if r not in before.roles]
            lost = [r for r in before.roles if r not in after.roles]

            if gained or lost:
                changes = {"Member": f"{after} ({after.id})"}
                if gained:
                    changes["Added"] = ", ".join(role.name for role in gained)
                if lost:
                    changes["Removed"] = ", ".join(role.name for role in lost)

                actor_id, actor_name = await self.resolve_audit_actor(
                    after.guild,
                    discord.AuditLogAction.member_role_update,
                    target_id=after.id,
                )

                await self.record_event(
                    after.guild,
                    "role",
                    "Member roles updated",
                    f"Roles changed for {after.display_name}.",
                    changes,
                    event_type="member_roles_update",
                    actor_id=actor_id,
                    actor_name=actor_name,
                )

    # ---- message events -------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return

        actor_id, actor_name = await self.resolve_audit_actor(
            message.guild,
            discord.AuditLogAction.message_delete,
            target_id=message.author.id,
        )

        content_preview = (message.content or "").strip()
        if len(content_preview) > 180:
            content_preview = content_preview[:177] + "…"
        if not content_preview:
            content_preview = "(empty or embed-only message)"

        channel_name = getattr(message.channel, "name", "unknown")
        description = (
            f"A message by {message.author.display_name} was deleted in "
            f"#{channel_name}."
        )
        if actor_name and actor_id != str(message.author.id):
            description = (
                f"{actor_name} deleted a message by "
                f"{message.author.display_name} in #{channel_name}."
            )

        await self.record_event(
            message.guild,
            "message",
            "Message deleted",
            description,
            {
                "Author": f"{message.author} ({message.author.id})",
                "Channel": channel_name,
                "Content": content_preview,
            },
            event_type="message_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: discord.Message,
        after: discord.Message,
    ) -> None:
        if after.guild is None or after.author.bot:
            return

        if before.content == after.content:
            return

        channel_name = getattr(after.channel, "name", "unknown")
        await self.record_event(
            after.guild,
            "message",
            "Message edited",
            (
                f"{after.author.display_name} edited a message in "
                f"#{channel_name}."
            ),
            {
                "Author": f"{after.author} ({after.author.id})",
                "Channel": channel_name,
                "Before": (before.content or "—")[:512],
                "After": (after.content or "—")[:512],
            },
            event_type="message_edit",
            actor_id=str(after.author.id),
            actor_name=str(after.author),
        )

    # ---- role events ------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            role.guild,
            discord.AuditLogAction.role_create,
            target_id=role.id,
        )
        await self.record_event(
            role.guild,
            "role",
            "Role created",
            f"Role **{role.name}** was created.",
            {"Role": role.name},
            event_type="role_create",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            role.guild,
            discord.AuditLogAction.role_delete,
            target_id=role.id,
        )
        await self.record_event(
            role.guild,
            "role",
            "Role deleted",
            f"Role **{role.name}** was deleted.",
            {"Role": role.name},
            event_type="role_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            after.guild,
            discord.AuditLogAction.role_update,
            target_id=after.id,
        )
        if before.name != after.name:
            await self.record_event(
                after.guild,
                "role",
                "Role renamed",
                f"Role **{before.name}** renamed to **{after.name}**.",
                {"Before": before.name, "After": after.name},
                event_type="role_update",
                actor_id=actor_id,
                actor_name=actor_name,
            )
        elif before.permissions != after.permissions:
            await self.record_event(
                after.guild,
                "role",
                "Role permissions updated",
                f"Permissions changed for role **{after.name}**.",
                {"Role": after.name},
                event_type="role_update",
                actor_id=actor_id,
                actor_name=actor_name,
            )

    # ---- channel events ----------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self,
        channel: discord.abc.GuildChannel,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            channel.guild,
            discord.AuditLogAction.channel_create,
            target_id=channel.id,
        )
        await self.record_event(
            channel.guild,
            "channel",
            "Channel created",
            f"Channel **#{channel.name}** was created.",
            {"Type": str(channel.type)},
            event_type="channel_create",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self,
        channel: discord.abc.GuildChannel,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            target_id=channel.id,
        )
        await self.record_event(
            channel.guild,
            "channel",
            "Channel deleted",
            f"Channel **#{channel.name}** was deleted.",
            {"Type": str(channel.type)},
            event_type="channel_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        changes: dict[str, str] = {}
        if getattr(before, "name", None) != getattr(after, "name", None):
            changes["Name"] = f"{before.name} → {after.name}"
        before_topic = getattr(before, "topic", None)
        after_topic = getattr(after, "topic", None)
        if before_topic != after_topic:
            changes["Topic"] = "updated"
        if not changes:
            return

        actor_id, actor_name = await self.resolve_audit_actor(
            after.guild,
            discord.AuditLogAction.channel_update,
            target_id=after.id,
        )
        await self.record_event(
            after.guild,
            "channel",
            "Channel updated",
            f"Channel **#{after.name}** was updated.",
            changes,
            event_type="channel_update",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    # ---- thread events -----------------------------------------------------

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread) -> None:
        parent_name = getattr(thread.parent, "name", "unknown")
        actor_id, actor_name = await self.resolve_audit_actor(
            thread.guild,
            discord.AuditLogAction.thread_create,
            target_id=thread.id,
        )
        await self.record_event(
            thread.guild,
            "thread",
            "Thread created",
            f"Thread **{thread.name}** was created in #{parent_name}.",
            {"Thread": thread.name, "Parent": parent_name},
            event_type="thread_create",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread) -> None:
        parent_name = getattr(thread.parent, "name", "unknown")
        actor_id, actor_name = await self.resolve_audit_actor(
            thread.guild,
            discord.AuditLogAction.thread_delete,
            target_id=thread.id,
        )
        await self.record_event(
            thread.guild,
            "thread",
            "Thread deleted",
            f"Thread **{thread.name}** was deleted from #{parent_name}.",
            {"Thread": thread.name, "Parent": parent_name},
            event_type="thread_delete",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_thread_update(
        self,
        before: discord.Thread,
        after: discord.Thread,
    ) -> None:
        changes: dict[str, str] = {}
        if before.name != after.name:
            changes["Name"] = f"{before.name} → {after.name}"
        if before.archived != after.archived:
            changes["Archived"] = str(after.archived)
        if before.locked != after.locked:
            changes["Locked"] = str(after.locked)
        if not changes:
            return

        actor_id, actor_name = await self.resolve_audit_actor(
            after.guild,
            discord.AuditLogAction.thread_update,
            target_id=after.id,
        )
        await self.record_event(
            after.guild,
            "thread",
            "Thread updated",
            f"Thread **{after.name}** was updated.",
            changes,
            event_type="thread_update",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    # ---- ban events --------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(
        self,
        guild: discord.Guild,
        user: discord.User | discord.Member,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            guild,
            discord.AuditLogAction.ban,
            target_id=user.id,
        )
        await self.record_event(
            guild,
            "member",
            "Member banned",
            f"{user} ({user.id}) was banned.",
            {"Member": f"{user} ({user.id})"},
            event_type="member_ban",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_member_unban(
        self,
        guild: discord.Guild,
        user: discord.User,
    ) -> None:
        actor_id, actor_name = await self.resolve_audit_actor(
            guild,
            discord.AuditLogAction.unban,
            target_id=user.id,
        )
        await self.record_event(
            guild,
            "member",
            "Member unbanned",
            f"{user} ({user.id}) was unbanned.",
            {"Member": f"{user} ({user.id})"},
            event_type="member_unban",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    # ---- bulk message + server + voice events ------------------------------

    @commands.Cog.listener()
    async def on_bulk_message_delete(
        self,
        messages: list[discord.Message],
    ) -> None:
        if not messages:
            return
        guild = messages[0].guild
        if guild is None:
            return
        channel_name = getattr(messages[0].channel, "name", "unknown")
        await self.record_event(
            guild,
            "message",
            "Messages bulk deleted",
            f"{len(messages)} messages were bulk deleted in #{channel_name}.",
            {"Channel": channel_name, "Count": str(len(messages))},
            event_type="message_bulk_delete",
        )

    @commands.Cog.listener()
    async def on_guild_update(
        self,
        before: discord.Guild,
        after: discord.Guild,
    ) -> None:
        changes: dict[str, str] = {}
        if before.name != after.name:
            changes["Name"] = f"{before.name} → {after.name}"
        if before.owner_id != after.owner_id:
            changes["Owner"] = "changed"
        if not changes:
            return

        actor_id, actor_name = await self.resolve_audit_actor(
            after,
            discord.AuditLogAction.guild_update,
        )
        await self.record_event(
            after,
            "server",
            "Server settings updated",
            f"Server **{after.name}** settings were updated.",
            changes,
            event_type="guild_update",
            actor_id=actor_id,
            actor_name=actor_name,
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel is None and after.channel is not None:
            await self.record_event(
                member.guild,
                "voice",
                "Joined voice",
                f"{member.display_name} joined voice **{after.channel.name}**.",
                {"Member": f"{member} ({member.id})", "Channel": after.channel.name},
                event_type="voice_join",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        elif before.channel is not None and after.channel is None:
            await self.record_event(
                member.guild,
                "voice",
                "Left voice",
                f"{member.display_name} left voice **{before.channel.name}**.",
                {"Member": f"{member} ({member.id})", "Channel": before.channel.name},
                event_type="voice_leave",
                actor_id=str(member.id),
                actor_name=str(member),
            )
        elif (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):
            await self.record_event(
                member.guild,
                "voice",
                "Moved voice channel",
                (
                    f"{member.display_name} moved from **{before.channel.name}** "
                    f"to **{after.channel.name}**."
                ),
                {
                    "Member": f"{member} ({member.id})",
                    "From": before.channel.name,
                    "To": after.channel.name,
                },
                event_type="voice_move",
                actor_id=str(member.id),
                actor_name=str(member),
            )
