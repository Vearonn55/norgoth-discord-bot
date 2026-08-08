"""Norgoth Discord bot: gateway client, guild sync, and event handlers."""

from __future__ import annotations

import logging
from typing import Any

import discord
import httpx
from discord.ext import commands, tasks

from bot.config import BotSettings
from bot.state import BotState, now_iso, welcome_status_key

logger = logging.getLogger("norgoth.bot")

WELCOME_MESSAGE_VARIABLES = (
    "{user}",
    "{username}",
    "{server}",
    "{member_count}",
    "{inviter}",
    "{inviter_count}",
)


def render_member_message(
    template: str,
    member: discord.Member | discord.User,
    guild: discord.Guild,
    *,
    inviter_name: str | None = None,
    inviter_count: int | None = None,
) -> str:
    return (
        template.replace("{user}", member.mention)
        .replace("{username}", member.name)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count))
        .replace("{inviter}", inviter_name or "unknown")
        .replace(
            "{inviter_count}",
            str(inviter_count) if inviter_count is not None else "0",
        )
    )


def serialize_guild_resources(guild: discord.Guild) -> dict[str, Any]:
    channels = [
        {
            "id": str(channel.id),
            "name": channel.name,
            "type": "text",
            "category": channel.category.name if channel.category else None,
        }
        for channel in guild.text_channels
    ]

    roles = [
        {
            "id": str(role.id),
            "name": role.name,
            "position": role.position,
            "managed": role.managed,
            "color": f"#{role.color.value:06x}",
        }
        for role in guild.roles
        if not role.is_default()
    ]

    categories = [
        {"id": str(category.id), "name": category.name}
        for category in guild.categories
    ]

    emojis = [
        {
            "id": str(emoji.id),
            "name": emoji.name,
            "animated": bool(emoji.animated),
        }
        for emoji in guild.emojis
    ]

    return {
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "member_count": guild.member_count,
        "channels": channels,
        "categories": categories,
        "roles": sorted(roles, key=lambda role: -int(role["position"])),
        "emojis": emojis,
        "updated_at": now_iso(),
    }


def serialize_guild_members(guild: discord.Guild) -> dict[str, Any]:
    members = [
        {
            "id": str(member.id),
            "name": member.name,
            "display_name": member.display_name,
            "bot": member.bot,
            "role_ids": [
                str(role.id) for role in member.roles if not role.is_default()
            ],
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        }
        for member in guild.members
    ]

    return {
        "guild_id": str(guild.id),
        "guild_name": guild.name,
        "members": members,
        "updated_at": now_iso(),
    }


class NorgothBot(commands.Bot):
    def __init__(self, settings: BotSettings) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.voice_states = True
        # Ban/unban gateway events for config-driven moderation logging.
        intents.moderation = True
        # Required for automod, auto-responses, and leveling. Must also be
        # enabled in the Discord Developer Portal (Message Content Intent).
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=settings.application_id,
        )

        self.settings = settings
        self.state = BotState(settings.redis_url)

    async def setup_hook(self) -> None:
        from bot.analytics import AnalyticsCog
        from bot.automod import AutoModCog
        from bot.autoresponder import AutoResponderCog
        from bot.campaigns import CampaignsCog
        from bot.embed_sync import EmbedSyncCog
        from bot.honeypot import HoneypotCog
        from bot.invites import InvitesCog
        from bot.leveling import LevelingCog
        from bot.moderation import ModerationCog
        from bot.notifications import NotificationsCog
        from bot.raid import RaidCog
        from bot.roles import RolesCog
        from bot.server_logging import ServerLoggingCog
        from bot.tickets import TicketCloseView, TicketPanelView, TicketsCog

        await self.add_cog(ModerationCog(self))
        await self.add_cog(AutoModCog(self))
        await self.add_cog(ServerLoggingCog(self))
        await self.add_cog(AnalyticsCog(self))
        await self.add_cog(LevelingCog(self))
        await self.add_cog(AutoResponderCog(self))
        await self.add_cog(RolesCog(self))
        await self.add_cog(InvitesCog(self))
        await self.add_cog(RaidCog(self))
        await self.add_cog(HoneypotCog(self))
        await self.add_cog(NotificationsCog(self))
        await self.add_cog(CampaignsCog(self))
        await self.add_cog(EmbedSyncCog(self))

        tickets_cog = TicketsCog(self)
        await self.add_cog(tickets_cog)
        # Persistent views so panel/close buttons survive bot restarts.
        self.add_view(TicketPanelView(tickets_cog))
        self.add_view(TicketCloseView(tickets_cog))
        self.heartbeat_loop.start()

    @tasks.loop(seconds=15)
    async def heartbeat_loop(self) -> None:
        try:
            await self.state.publish_heartbeat()
            await self.publish_status()
        except Exception:  # noqa: BLE001 - keep the loop alive on Redis hiccups
            logger.exception("Failed to publish bot heartbeat")

    @heartbeat_loop.before_loop
    async def before_heartbeat(self) -> None:
        await self.wait_until_ready()

    async def publish_status(self) -> None:
        await self.state.publish_status(
            {
                "connected": True,
                "user_id": str(self.user.id) if self.user else None,
                "user_name": str(self.user) if self.user else None,
                "application_id": (
                    str(self.settings.application_id)
                    if self.settings.application_id
                    else None
                ),
                "latency_ms": round(self.latency * 1000, 1),
                "intents": {
                    "guilds": self.intents.guilds,
                    "members": self.intents.members,
                    "message_content": self.intents.message_content,
                },
                "guilds": [
                    {
                        "id": str(guild.id),
                        "name": guild.name,
                        "member_count": guild.member_count,
                    }
                    for guild in self.guilds
                ],
                "updated_at": now_iso(),
            }
        )

    async def sync_guild(self, guild: discord.Guild) -> None:
        await self.state.publish_guild_resources(
            guild.id,
            serialize_guild_resources(guild),
        )
        await self.sync_guild_members(guild)
        await self.register_guild_with_api(guild)

    async def sync_guild_members(self, guild: discord.Guild) -> None:
        try:
            await self.state.publish_guild_members(
                guild.id,
                serialize_guild_members(guild),
            )
        except Exception:  # noqa: BLE001 - snapshot publishing must not break events
            logger.exception("Failed to publish member snapshot for guild %s", guild.id)

    async def register_guild_with_api(self, guild: discord.Guild) -> None:
        """Upsert the guild into the verification domain of the API."""

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(
                    f"{self.settings.api_base_url}/api/v1/guilds/{guild.id}",
                    json={
                        "discord_guild_name": guild.name,
                        "discord_owner_id": str(guild.owner_id),
                    },
                )

            if response.status_code not in (200, 201):
                logger.warning(
                    "Guild registration returned HTTP %s: %s",
                    response.status_code,
                    response.text,
                )
        except httpx.HTTPError:
            logger.exception("Guild registration with the API failed")

    async def on_ready(self) -> None:
        guild_names = ", ".join(guild.name for guild in self.guilds) or "none"
        logger.info("Bot ready as %s. Guilds: %s", self.user, guild_names)

        for guild in self.guilds:
            await self.sync_guild(guild)
            # Guild-scoped sync keeps slash-command iteration instant.
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)

        await self.publish_status()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("Joined guild %s (%s)", guild.name, guild.id)
        await self.sync_guild(guild)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        await self.publish_status()

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self.sync_guild(channel.guild)

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        await self.sync_guild(channel.guild)

    async def on_guild_role_create(self, role: discord.Role) -> None:
        await self.sync_guild(role.guild)

    async def on_guild_role_delete(self, role: discord.Role) -> None:
        await self.sync_guild(role.guild)

    async def on_member_update(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        if before.roles != after.roles:
            await self.sync_guild_members(after.guild)

    async def resolve_inviter(self, member: discord.Member) -> tuple[str | None, int | None]:
        """Overridden by the invite tracking cog when it is loaded."""

        return (None, None)

    async def publish_welcome_status(
        self,
        guild_id: int,
        *,
        ok: bool,
        reason: str,
        member_name: str | None = None,
        channel_id: str | None = None,
    ) -> None:
        try:
            await self.state.set_json(
                welcome_status_key(guild_id),
                {
                    "ok": ok,
                    "reason": reason,
                    "member": member_name,
                    "channel_id": channel_id,
                    "attempted_at": now_iso(),
                },
            )
        except Exception:  # noqa: BLE001 - status reporting must not break events
            logger.exception("Failed to publish welcome status")

    async def deliver_welcome_message(self, member: discord.Member) -> None:
        guild = member.guild
        config = await self.state.get_automation_config(guild.id)

        if not config.get("welcome_enabled"):
            logger.info(
                "Welcome skipped in guild %s: welcome is disabled.", guild.id
            )
            await self.publish_welcome_status(
                guild.id,
                ok=False,
                reason=(
                    "Welcome messages are disabled in the dashboard. "
                    "Enable them and save, or use Send test welcome message."
                ),
                member_name=member.name,
            )
            return

        channel_id = config.get("welcome_channel_id")

        if not channel_id:
            logger.warning(
                "Welcome skipped in guild %s: no welcome channel configured.",
                guild.id,
            )
            await self.publish_welcome_status(
                guild.id,
                ok=False,
                reason="Welcome is enabled but no channel is selected.",
                member_name=member.name,
            )
            return

        channel = guild.get_channel(int(channel_id))

        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "Welcome skipped in guild %s: channel %s not found or not a "
                "text channel.",
                guild.id,
                channel_id,
            )
            await self.publish_welcome_status(
                guild.id,
                ok=False,
                reason="The configured welcome channel no longer exists.",
                member_name=member.name,
                channel_id=str(channel_id),
            )
            return

        permissions = channel.permissions_for(guild.me)

        if not (permissions.view_channel and permissions.send_messages):
            logger.warning(
                "Welcome skipped in guild %s: missing View Channel / Send "
                "Messages permission in #%s.",
                guild.id,
                channel.name,
            )
            await self.publish_welcome_status(
                guild.id,
                ok=False,
                reason=(
                    f"The bot lacks View Channel / Send Messages in #{channel.name}."
                ),
                member_name=member.name,
                channel_id=str(channel_id),
            )
            return

        template = config.get("welcome_message") or "Welcome to {server}, {user}!"

        inviter_name: str | None = None
        inviter_count: int | None = None

        try:
            inviter_name, inviter_count = await self.resolve_inviter(member)
        except Exception:  # noqa: BLE001 - invite attribution must not block welcome
            logger.exception(
                "Invite attribution failed for %s in guild %s",
                member,
                guild.id,
            )

        try:
            await channel.send(
                render_member_message(
                    template,
                    member,
                    guild,
                    inviter_name=inviter_name,
                    inviter_count=inviter_count,
                )
            )
        except discord.HTTPException as error:
            logger.exception(
                "Failed to send welcome message in guild %s", guild.id
            )
            await self.publish_welcome_status(
                guild.id,
                ok=False,
                reason=f"Discord rejected the message: {error}",
                member_name=member.name,
                channel_id=str(channel_id),
            )
            return

        await self.publish_welcome_status(
            guild.id,
            ok=True,
            reason=f"Welcome message delivered to #{channel.name}.",
            member_name=member.name,
            channel_id=str(channel_id),
        )

    async def deliver_leave_message(
        self,
        guild: discord.Guild,
        member: discord.Member | discord.User,
    ) -> None:
        config = await self.state.get_automation_config(guild.id)

        if not config.get("leave_enabled"):
            logger.info(
                "Leave message skipped in guild %s: leave is disabled.",
                guild.id,
            )
            return

        channel_id = config.get("leave_channel_id") or config.get(
            "welcome_channel_id"
        )

        if not channel_id:
            logger.warning(
                "Leave message skipped in guild %s: no channel configured.",
                guild.id,
            )
            return

        channel = guild.get_channel(int(channel_id))

        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "Leave message skipped in guild %s: channel %s unavailable.",
                guild.id,
                channel_id,
            )
            return

        permissions = channel.permissions_for(guild.me)

        if not (permissions.view_channel and permissions.send_messages):
            logger.warning(
                "Leave message skipped in guild %s: missing send permission "
                "in #%s.",
                guild.id,
                channel.name,
            )
            return

        template = config.get("leave_message") or "{username} has left {server}."

        try:
            await channel.send(render_member_message(template, member, guild))
            logger.info(
                "Leave message delivered for %s in guild %s (#%s).",
                member,
                guild.id,
                channel.name,
            )
        except discord.HTTPException:
            logger.exception("Failed to send leave message in guild %s", guild.id)

    async def apply_auto_role(self, member: discord.Member) -> None:
        config = await self.state.get_automation_config(member.guild.id)

        if not config.get("auto_role_enabled"):
            return

        role_ids: list[str] = []
        for role_id in config.get("auto_role_ids") or []:
            if isinstance(role_id, str) and role_id.isdigit() and role_id not in role_ids:
                role_ids.append(role_id)

        legacy = config.get("auto_role_id")
        if isinstance(legacy, str) and legacy.isdigit() and legacy not in role_ids:
            role_ids.insert(0, legacy)

        if not role_ids:
            return

        for role_id in role_ids:
            role = member.guild.get_role(int(role_id))

            if role is None:
                logger.warning(
                    "Auto-role skipped in guild %s: role %s no longer exists.",
                    member.guild.id,
                    role_id,
                )
                continue

            try:
                await member.add_roles(role, reason="Norgoth auto-role")
            except discord.Forbidden:
                logger.warning(
                    "Missing permission to grant auto-role %s in guild %s "
                    "(is the bot role above it?)",
                    role.id,
                    member.guild.id,
                )
            except discord.HTTPException:
                logger.exception(
                    "Failed to grant auto-role in guild %s",
                    member.guild.id,
                )

    async def on_member_join(self, member: discord.Member) -> None:
        logger.info(
            "Member joined guild %s: %s (%s)",
            member.guild.id,
            member,
            member.id,
        )

        try:
            await self.sync_guild_members(member.guild)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to sync members after join in guild %s", member.guild.id)

        if member.bot:
            return

        try:
            if await self.state.is_module_enabled(member.guild.id, "welcome"):
                await self.deliver_welcome_message(member)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Welcome delivery crashed for %s in guild %s",
                member,
                member.guild.id,
            )
            await self.publish_welcome_status(
                member.guild.id,
                ok=False,
                reason="Welcome handler crashed — check bot logs.",
                member_name=member.name,
            )

        try:
            if await self.state.is_module_enabled(member.guild.id, "autorole"):
                await self.apply_auto_role(member)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Auto-role crashed for %s in guild %s",
                member,
                member.guild.id,
            )

    async def on_member_remove(self, member: discord.Member) -> None:
        logger.info(
            "Member left guild %s: %s (%s)",
            member.guild.id,
            member,
            member.id,
        )

        try:
            await self.sync_guild_members(member.guild)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to sync members after leave in guild %s",
                member.guild.id,
            )

        if member.bot:
            return

        try:
            if await self.state.is_module_enabled(member.guild.id, "welcome"):
                await self.deliver_leave_message(member.guild, member)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Leave message crashed for %s in guild %s",
                member,
                member.guild.id,
            )

    async def close(self) -> None:
        try:
            await self.state.publish_status({"connected": False, "updated_at": now_iso()})
            await self.state.close()
        finally:
            await super().close()
