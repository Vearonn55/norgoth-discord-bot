"""Ticket system: panel button, private ticket channels, close + transcript."""

from __future__ import annotations

import json
import logging
import os
import secrets
import uuid
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from bot.state import now_iso
from bot.ticket_log_fields import (
    build_closed_ticket_log_fields,
    build_opened_ticket_log_fields,
    is_ticket_already_closed,
)

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.tickets")

OPEN_BUTTON_ID = "norgoth:ticket:open"
CLOSE_BUTTON_ID = "norgoth:ticket:close"

TRANSCRIPT_MESSAGE_LIMIT = 500
SHARE_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 90  # 90 days


def tickets_config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:config"


def ticket_panels_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:panels"


def tickets_records_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:records"


def tickets_counter_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:counter"


def ticket_transcript_key(guild_id: int | str, ticket_id: str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:transcript:{ticket_id}"


def ticket_share_key(token: str) -> str:
    return f"norgoth:tickets:share:{token}"


def dashboard_base_url() -> str:
    return (
        os.getenv("NEXT_PUBLIC_DASHBOARD_URL", "").strip()
        or os.getenv("NORGOTH_DASHBOARD_URL", "").strip()
        or "http://127.0.0.1:3000"
    ).rstrip("/")


class TicketPanelView(discord.ui.View):
    """Persistent view attached to the panel message."""

    def __init__(self, cog: "TicketsCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id=OPEN_BUTTON_ID,
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_open_ticket(interaction)


class TicketCloseView(discord.ui.View):
    """Persistent view attached to each ticket channel's intro message."""

    def __init__(self, cog: "TicketsCog") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id=CLOSE_BUTTON_ID,
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.handle_close_ticket(interaction)


class TicketsCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def get_config(self, guild_id: int) -> dict[str, Any]:
        return await self.bot.state.get_json(tickets_config_key(guild_id))

    async def read_panels(self, guild_id: int) -> list[dict[str, Any]]:
        raw = await self.bot.state.redis.get(ticket_panels_key(guild_id))
        if not raw:
            return []
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            return []
        panels = stored.get("panels") if isinstance(stored, dict) else None
        return panels if isinstance(panels, list) else []

    async def resolve_panel_for_message(
        self, guild_id: int, message_id: int | None
    ) -> dict[str, Any] | None:
        """Match the clicked panel message to its stored panel config.

        The open button uses a static custom_id, so the panel is identified by
        the message it was posted on rather than the interaction data.
        """

        if message_id is None:
            return None
        for panel in await self.read_panels(guild_id):
            if (
                isinstance(panel, dict)
                and str(panel.get("message_id")) == str(message_id)
            ):
                return panel
        return None

    @staticmethod
    def _format_member_identity(user: discord.abc.User) -> str:
        """Human-readable Discord identity: Display Name (@username)."""

        display = getattr(user, "display_name", None) or getattr(user, "global_name", None)
        username = getattr(user, "name", None) or str(user)
        if display and display != username:
            return f"{display} (@{username})"
        return f"@{username}" if username else str(user)

    @staticmethod
    def _closed_ticket_embed(
        guild: discord.Guild,
        record: dict[str, Any],
        closed_by: str,
        *,
        audience: str,
    ) -> discord.Embed:
        """Build the closed-ticket embed shared by the opener DM and log post.

        Both use the same visual format; the log variant adds opener/closer
        fields useful to staff.
        """

        number = record.get("number")
        if audience == "dm":
            description = (
                f"Your support ticket in **{guild.name}** was closed by "
                f"{closed_by}."
            )
        else:
            description = (
                f"Support ticket opened by "
                f"{record.get('opener_name') or 'a member'} in "
                f"**{guild.name}** was closed by {closed_by}."
            )

        embed = discord.Embed(
            title=f"Ticket #{number} closed",
            description=description,
            color=discord.Color.dark_grey(),
        )
        embed.add_field(
            name="Channel",
            value=record.get("channel_name") or "ticket",
            inline=True,
        )
        if audience != "dm":
            embed.add_field(
                name="Opened by",
                value=record.get("opener_name") or "unknown",
                inline=True,
            )
            embed.add_field(name="Closed by", value=closed_by, inline=True)
            if record.get("opened_at"):
                embed.add_field(
                    name="Opened at",
                    value=str(record["opened_at"]),
                    inline=True,
                )
            if record.get("closed_at"):
                embed.add_field(
                    name="Closed at",
                    value=str(record["closed_at"]),
                    inline=True,
                )
        return embed

    @staticmethod
    def _transcript_view(transcript_url: str) -> discord.ui.View:
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="View transcript",
                style=discord.ButtonStyle.link,
                url=transcript_url,
            )
        )
        return view

    async def find_open_ticket_by_channel(
        self,
        guild_id: int,
        channel_id: int,
    ) -> dict[str, Any] | None:
        records = await self.bot.state.redis.hgetall(tickets_records_key(guild_id))

        for raw in records.values():
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if (
                isinstance(record, dict)
                and str(record.get("channel_id")) == str(channel_id)
                and record.get("status") == "open"
            ):
                return record

        return None

    async def find_open_ticket_by_opener(
        self,
        guild_id: int,
        opener_id: int,
    ) -> dict[str, Any] | None:
        records = await self.bot.state.redis.hgetall(tickets_records_key(guild_id))

        for raw in records.values():
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if (
                isinstance(record, dict)
                and str(record.get("opener_id")) == str(opener_id)
                and record.get("status") == "open"
            ):
                return record

        return None

    async def save_record(self, guild_id: int, record: dict[str, Any]) -> None:
        await self.bot.state.redis.hset(
            tickets_records_key(guild_id),
            record["id"],
            json.dumps(record),
        )

    async def _log_ticket_event(
        self,
        guild: discord.Guild,
        *,
        event_type: str,
        action: str,
        description: str,
        fields: dict[str, str],
    ) -> None:
        """Route a ticket event through the central logging wizard.

        Ticket open/close now flow through the same config-driven logging as
        every other server event, so admins pick the destination channel in the
        Logging Configurations wizard rather than a per-panel field.
        """

        cog = self.bot.get_cog("ServerLoggingCog")
        if cog is None:
            return
        try:
            await cog.record_event(
                guild,
                "tickets",
                action,
                description,
                fields,
                event_type=event_type,
            )
        except Exception:  # noqa: BLE001 - logging must never break tickets
            logger.exception("Failed to record ticket log event %s", event_type)

    # ---- open ---------------------------------------------------------

    async def handle_open_ticket(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild

        if guild is None or not isinstance(interaction.user, discord.Member):
            return

        if not await self.bot.state.is_module_enabled(guild.id, "tickets"):
            await interaction.response.send_message(
                "The ticket module is disabled in the Norgoth dashboard.",
                ephemeral=True,
            )
            return

        existing = await self.find_open_ticket_by_opener(
            guild.id, interaction.user.id
        )

        if existing:
            await interaction.response.send_message(
                f"You already have an open ticket: <#{existing['channel_id']}>",
                ephemeral=True,
            )
            return

        config = await self.get_config(guild.id)

        # Resolve the panel that was clicked to get panel-specific routing.
        # Fall back to the legacy global config for un-migrated panels.
        panel = await self.resolve_panel_for_message(
            guild.id,
            interaction.message.id if interaction.message else None,
        )
        open_category_id = (panel or {}).get("open_category_id") or config.get(
            "category_id"
        )

        category: discord.CategoryChannel | None = None

        if open_category_id:
            channel = guild.get_channel(int(open_category_id))
            if isinstance(channel, discord.CategoryChannel):
                category = channel

        support_role_ids = [
            int(role_id) for role_id in config.get("support_role_ids", [])
        ]

        overwrites: dict[
            discord.Role | discord.Member, discord.PermissionOverwrite
        ] = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            ),
        }

        for role_id in support_role_ids:
            role = guild.get_role(role_id)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

        number = await self.bot.state.redis.incr(tickets_counter_key(guild.id))
        channel_name = f"ticket-{number:04d}"

        try:
            ticket_channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I need the Manage Channels permission to create ticket "
                "channels.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            logger.exception("Failed to create ticket channel in %s", guild.id)
            await interaction.response.send_message(
                "Could not create the ticket channel. Please try again.",
                ephemeral=True,
            )
            return

        opener_identity = self._format_member_identity(interaction.user)
        panel_name = None
        if isinstance(panel, dict):
            panel_name = panel.get("name") or panel.get("title") or panel.get("id")

        record = {
            "id": str(uuid.uuid4()),
            "number": number,
            "guild_id": str(guild.id),
            "channel_id": str(ticket_channel.id),
            "channel_name": channel_name,
            "opener_id": str(interaction.user.id),
            "opener_name": opener_identity,
            "status": "open",
            "opened_at": now_iso(),
            "closed_at": None,
            "closed_by": None,
            "panel_id": (panel or {}).get("id"),
            "panel_name": panel_name,
            "open_category_id": (
                str(open_category_id) if open_category_id else None
            ),
        }
        await self.save_record(guild.id, record)

        welcome_text = str(
            config.get("welcome_text")
            or "Support will be with you shortly. Describe your issue here."
        )

        embed = discord.Embed(
            title=f"Ticket #{number:04d}",
            description=welcome_text,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Opened by", value=interaction.user.mention)
        embed.set_footer(text="Use the button below or /ticket close to close.")

        try:
            await ticket_channel.send(
                content=interaction.user.mention,
                embed=embed,
                view=TicketCloseView(self),
            )
        except discord.HTTPException:
            logger.exception("Failed to send ticket intro message")

        opened_fields = build_opened_ticket_log_fields(
            number=number,
            opener_identity=opener_identity,
            opener_id=str(interaction.user.id),
            opened_at=record["opened_at"],
            panel_name=str(panel_name) if panel_name else None,
        )

        await self._log_ticket_event(
            guild,
            event_type="ticket_opened",
            action="🎫 Ticket opened",
            description=(
                f"**{opener_identity}** opened ticket **#{number:04d}**."
            ),
            fields=opened_fields,
        )

        await interaction.response.send_message(
            f"Your ticket is ready: {ticket_channel.mention}",
            ephemeral=True,
        )

    # ---- close --------------------------------------------------------------

    async def handle_close_ticket(
        self,
        interaction: discord.Interaction,
    ) -> None:
        guild = interaction.guild

        if guild is None or interaction.channel is None:
            return

        record = await self.find_open_ticket_by_channel(
            guild.id, interaction.channel.id
        )

        if record is None:
            await interaction.response.send_message(
                "This channel is not an open ticket.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Closing this ticket: saving the transcript and deleting the "
            "channel…"
        )

        await self.close_ticket(
            guild,
            interaction.channel,
            record,
            closed_by=self._format_member_identity(interaction.user),
        )

    async def close_ticket(
        self,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel | discord.abc.Messageable,
        record: dict[str, Any],
        closed_by: str,
    ) -> None:
        # Idempotency: a retry must not regenerate transcripts or re-emit the
        # Closed Ticket log for an already-closed ticket.
        if is_ticket_already_closed(record):
            logger.info(
                "Ignoring duplicate close for ticket %s in guild %s",
                record.get("id"),
                guild.id,
            )
            return

        transcript_lines: list[str] = []

        if isinstance(channel, discord.TextChannel):
            try:
                async for message in channel.history(
                    limit=TRANSCRIPT_MESSAGE_LIMIT,
                    oldest_first=True,
                ):
                    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    content = message.content or ""

                    if message.embeds:
                        content += " [embed]"
                    if message.attachments:
                        content += " " + " ".join(
                            attachment.url for attachment in message.attachments
                        )

                    transcript_lines.append(
                        f"[{timestamp}] {message.author}: {content.strip()}"
                    )
            except discord.HTTPException:
                logger.exception("Failed to fetch ticket history")

        transcript = "\n".join(transcript_lines) or "(no messages)"

        await self.bot.state.redis.set(
            ticket_transcript_key(guild.id, record["id"]),
            transcript,
        )

        closed_at = now_iso()
        share_token = secrets.token_urlsafe(24)
        share_payload = {
            "guild_id": str(guild.id),
            "guild_name": guild.name,
            "ticket_id": record["id"],
            "ticket_number": record.get("number"),
            "opener_id": record.get("opener_id"),
            "opener_name": record.get("opener_name"),
            "opened_at": record.get("opened_at"),
            "closed_by": closed_by,
            "closed_at": closed_at,
            "channel_name": record.get("channel_name"),
            "panel_name": record.get("panel_name"),
            "transcript": transcript,
        }
        await self.bot.state.redis.set(
            ticket_share_key(share_token),
            json.dumps(share_payload),
            ex=SHARE_TOKEN_TTL_SECONDS,
        )

        record["status"] = "closed"
        record["closed_at"] = closed_at
        record["closed_by"] = closed_by
        record["share_token"] = share_token
        await self.save_record(guild.id, record)

        transcript_url = (
            f"{dashboard_base_url()}/en/tickets/transcript/{share_token}"
        )

        opener_id = record.get("opener_id")
        if opener_id:
            try:
                opener = await self.bot.fetch_user(int(opener_id))
                await opener.send(
                    embed=self._closed_ticket_embed(
                        guild, record, closed_by, audience="dm"
                    ),
                    view=self._transcript_view(transcript_url),
                )
            except (discord.HTTPException, discord.Forbidden, ValueError):
                logger.info(
                    "Could not DM ticket opener %s for closed ticket %s",
                    opener_id,
                    record.get("id"),
                )

        # Closed-ticket logging flows through the central logging wizard
        # (Tickets group). The transcript deep-link reuses the same share
        # token as the opener DM (single source of truth).
        closed_fields = build_closed_ticket_log_fields(
            number=record.get("number"),
            opener_name=record.get("opener_name"),
            closed_by=closed_by,
            channel_name=record.get("channel_name"),
            transcript_url=transcript_url,
            opened_at=record.get("opened_at"),
            closed_at=closed_at,
            panel_name=record.get("panel_name"),
        )

        await self._log_ticket_event(
            guild,
            event_type="ticket_closed",
            action="🔒 Ticket closed",
            description=(
                f"Ticket **#{record.get('number')}** opened by "
                f"**{record.get('opener_name') or 'a member'}** was closed by "
                f"**{closed_by}**."
            ),
            fields=closed_fields,
        )

        if isinstance(channel, discord.TextChannel):
            try:
                await channel.delete(reason=f"Ticket closed by {closed_by}")
            except discord.HTTPException:
                logger.exception("Failed to delete ticket channel")

    # ---- slash command -----------------------------------------------------

    ticket_group = app_commands.Group(
        name="ticket",
        description="Ticket management",
    )

    @ticket_group.command(name="close", description="Close this ticket")
    async def ticket_close(self, interaction: discord.Interaction) -> None:
        await self.handle_close_ticket(interaction)
