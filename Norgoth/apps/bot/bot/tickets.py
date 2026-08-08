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

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.tickets")

OPEN_BUTTON_ID = "norgoth:ticket:open"
CLOSE_BUTTON_ID = "norgoth:ticket:close"

TRANSCRIPT_MESSAGE_LIMIT = 500
SHARE_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 90  # 90 days


def tickets_config_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:tickets:config"


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

        category: discord.CategoryChannel | None = None
        category_id = config.get("category_id")

        if category_id:
            channel = guild.get_channel(int(category_id))
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

        record = {
            "id": str(uuid.uuid4()),
            "number": number,
            "guild_id": str(guild.id),
            "channel_id": str(ticket_channel.id),
            "channel_name": channel_name,
            "opener_id": str(interaction.user.id),
            "opener_name": str(interaction.user),
            "status": "open",
            "opened_at": now_iso(),
            "closed_at": None,
            "closed_by": None,
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
            closed_by=str(interaction.user),
        )

    async def close_ticket(
        self,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel | discord.abc.Messageable,
        record: dict[str, Any],
        closed_by: str,
    ) -> None:
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

        share_token = secrets.token_urlsafe(24)
        share_payload = {
            "guild_id": str(guild.id),
            "guild_name": guild.name,
            "ticket_id": record["id"],
            "ticket_number": record.get("number"),
            "opener_id": record.get("opener_id"),
            "opener_name": record.get("opener_name"),
            "closed_by": closed_by,
            "closed_at": now_iso(),
            "channel_name": record.get("channel_name"),
            "transcript": transcript,
        }
        await self.bot.state.redis.set(
            ticket_share_key(share_token),
            json.dumps(share_payload),
            ex=SHARE_TOKEN_TTL_SECONDS,
        )

        record["status"] = "closed"
        record["closed_at"] = share_payload["closed_at"]
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
                dm_embed = discord.Embed(
                    title=f"Ticket #{record.get('number')} closed",
                    description=(
                        f"Your support ticket in **{guild.name}** was closed "
                        f"by {closed_by}."
                    ),
                    color=discord.Color.dark_grey(),
                )
                dm_embed.add_field(
                    name="Channel",
                    value=record.get("channel_name") or "ticket",
                    inline=True,
                )
                view = discord.ui.View()
                view.add_item(
                    discord.ui.Button(
                        label="View transcript",
                        style=discord.ButtonStyle.link,
                        url=transcript_url,
                    )
                )
                await opener.send(embed=dm_embed, view=view)
            except (discord.HTTPException, discord.Forbidden, ValueError):
                logger.info(
                    "Could not DM ticket opener %s for closed ticket %s",
                    opener_id,
                    record.get("id"),
                )

        config = await self.get_config(guild.id)
        log_channel_id = config.get("log_channel_id")
        if log_channel_id:
            log_channel = guild.get_channel(int(log_channel_id))
            if isinstance(log_channel, discord.TextChannel):
                log_embed = discord.Embed(
                    title=f"Ticket #{record.get('number')} closed",
                    color=discord.Color.orange(),
                )
                log_embed.add_field(
                    name="Opened by",
                    value=record.get("opener_name") or "unknown",
                    inline=True,
                )
                log_embed.add_field(
                    name="Closed by",
                    value=closed_by,
                    inline=True,
                )
                log_embed.add_field(
                    name="Channel",
                    value=record.get("channel_name") or "ticket",
                    inline=True,
                )
                log_embed.add_field(
                    name="Transcript",
                    value=f"[Open transcript]({transcript_url})",
                    inline=False,
                )
                try:
                    await log_channel.send(embed=log_embed)
                except discord.HTTPException:
                    logger.exception("Failed to post closed-ticket log")

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
