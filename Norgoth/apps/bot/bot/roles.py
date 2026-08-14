"""Role management: self-assign role-menu buttons/select/reactions and /role commands."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from bot.state import now_iso

if TYPE_CHECKING:
    from bot.client import NorgothBot

logger = logging.getLogger("norgoth.bot.roles")

ROLE_MENU_PREFIX = "norgoth:rolemenu:"


def _emoji_matches(
    stored: str,
    display: str,
    name: str | None,
    emoji_id: int | None,
) -> bool:
    if not stored:
        return False
    if stored == display or (name and stored == name):
        return True
    # Wire formats: name:id / a:name:id / <:name:id>
    if emoji_id is not None and str(emoji_id) in stored:
        if name and name in stored:
            return True
        if stored.endswith(f":{emoji_id}"):
            return True
    return False


def role_menus_key(guild_id: int | str) -> str:
    return f"norgoth:guild:{guild_id}:rolemenus"


class RolesCog(commands.Cog):
    def __init__(self, bot: "NorgothBot") -> None:
        self.bot = bot

    async def load_menus(self, guild_id: int) -> list[dict[str, Any]]:
        raw = await self.bot.state.redis.get(role_menus_key(guild_id))
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        menus = parsed.get("menus") if isinstance(parsed, dict) else None
        return menus if isinstance(menus, list) else []

    async def apply_role_mode(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        role: discord.Role,
        mode: str,
    ) -> str:
        if role >= guild.me.top_role:  # type: ignore[operator]
            return (
                f"I can't manage **{role.name}** because it is above my "
                "highest role."
            )

        try:
            if mode == "give":
                if role in member.roles:
                    return f"You already have **{role.name}**."
                await member.add_roles(role, reason="Role menu give")
                return f"You now have **{role.name}**."
            if mode == "take":
                if role not in member.roles:
                    return f"You don't have **{role.name}**."
                await member.remove_roles(role, reason="Role menu take")
                return f"Removed **{role.name}**."
            # toggle
            if role in member.roles:
                await member.remove_roles(role, reason="Role menu self-remove")
                return f"Removed **{role.name}**."
            await member.add_roles(role, reason="Role menu self-assign")
            return f"You now have **{role.name}**."
        except discord.Forbidden:
            return "I'm missing the Manage Roles permission."
        except discord.HTTPException:
            logger.exception("Role menu update failed for role %s", role.id)
            return "Something went wrong while updating your roles."

    def parse_custom_id(self, custom_id: str) -> tuple[str, str] | None:
        """Return (mode, role_id) from button/select custom ids."""
        if not custom_id.startswith(ROLE_MENU_PREFIX):
            return None
        rest = custom_id.removeprefix(ROLE_MENU_PREFIX)
        # legacy: norgoth:rolemenu:{role_id}
        if rest.isdigit():
            return "toggle", rest
        # select menu id: select:{menu_id} — handled separately
        if rest.startswith("select:"):
            return None
        # norgoth:rolemenu:{mode}:{role_id}
        parts = rest.split(":", 1)
        if len(parts) != 2:
            return None
        mode, role_id = parts
        if mode not in {"toggle", "give", "take"} or not role_id.isdigit():
            return None
        return mode, role_id

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id", "")
        if not isinstance(custom_id, str) or not custom_id.startswith(
            ROLE_MENU_PREFIX
        ):
            return

        guild = interaction.guild
        if guild is None or not isinstance(interaction.user, discord.Member):
            return

        if not await self.bot.state.is_module_enabled(guild.id, "roles"):
            await interaction.response.send_message(
                "The role menu module is disabled in the Norgoth dashboard.",
                ephemeral=True,
            )
            return

        menus = await self.load_menus(guild.id)
        allowed_role_ids = {
            str(entry.get("role_id"))
            for menu in menus
            if str(menu.get("message_id") or "") == str(interaction.message.id if interaction.message else "")
            for entry in (menu.get("roles") or [])
            if entry.get("role_id")
        }
        if not allowed_role_ids and interaction.message is not None:
            # Fall back to any configured menu in this guild if message_id drifted.
            allowed_role_ids = {
                str(entry.get("role_id"))
                for menu in menus
                for entry in (menu.get("roles") or [])
                if entry.get("role_id")
            }

        # Select menu
        if custom_id.startswith(f"{ROLE_MENU_PREFIX}select:"):
            values = data.get("values") or []
            if not values:
                return
            value = str(values[0])
            mode, _, role_id = value.partition(":")
            if not role_id:
                mode, role_id = "toggle", value
            if role_id not in allowed_role_ids:
                await interaction.response.send_message(
                    "This role is no longer on the menu.",
                    ephemeral=True,
                )
                return
            role = guild.get_role(int(role_id))
            if role is None:
                await interaction.response.send_message(
                    "This role no longer exists.",
                    ephemeral=True,
                )
                return
            message = await self.apply_role_mode(
                guild=guild,
                member=interaction.user,
                role=role,
                mode=mode or "toggle",
            )
            await interaction.response.send_message(message, ephemeral=True)
            return

        parsed = self.parse_custom_id(custom_id)
        if parsed is None:
            return
        mode, role_id = parsed
        if role_id not in allowed_role_ids:
            await interaction.response.send_message(
                "This role is no longer on the menu.",
                ephemeral=True,
            )
            return
        role = guild.get_role(int(role_id))
        if role is None:
            await interaction.response.send_message(
                "This role no longer exists. Ask an admin to update the menu.",
                ephemeral=True,
            )
            return

        message = await self.apply_role_mode(
            guild=guild,
            member=interaction.user,
            role=role,
            mode=mode,
        )
        await interaction.response.send_message(message, ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self._handle_reaction(payload, added=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self._handle_reaction(payload, added=False)

    async def _handle_reaction(
        self,
        payload: discord.RawReactionActionEvent,
        *,
        added: bool,
    ) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        if not await self.bot.state.is_module_enabled(payload.guild_id, "roles"):
            return

        menus = await self.load_menus(payload.guild_id)
        menu = next(
            (
                m
                for m in menus
                if str(m.get("message_id") or "") == str(payload.message_id)
                and (m.get("interaction") or "buttons") == "reactions"
            ),
            None,
        )
        if menu is None:
            return

        emoji = str(payload.emoji)
        emoji_name = getattr(payload.emoji, "name", None)
        emoji_id = getattr(payload.emoji, "id", None)
        entry = next(
            (
                r
                for r in menu.get("roles") or []
                if _emoji_matches(str(r.get("emoji") or ""), emoji, emoji_name, emoji_id)
            ),
            None,
        )
        if not entry:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(int(entry["role_id"]))
        if member is None or role is None:
            return

        mode = entry.get("mode") or "toggle"
        if mode == "toggle":
            mode = "give" if added else "take"
        elif mode == "give" and not added:
            return
        elif mode == "take" and added:
            return
        elif mode == "take" and not added:
            mode = "take"
        elif mode == "give" and added:
            mode = "give"

        await self.apply_role_mode(
            guild=guild, member=member, role=role, mode=mode
        )

    # ---- moderator /role commands -----------------------------------------

    role_group = app_commands.Group(
        name="role",
        description="Add or remove a role from a member",
        default_permissions=discord.Permissions(manage_roles=True),
    )

    async def check_hierarchy(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> str | None:
        guild = interaction.guild
        assert guild is not None

        if role.managed:
            return f"**{role.name}** is managed by an integration."

        if role >= guild.me.top_role:
            return (
                f"I can't manage **{role.name}**: it is above my highest role."
            )

        if (
            isinstance(interaction.user, discord.Member)
            and interaction.user != guild.owner
            and role >= interaction.user.top_role
        ):
            return (
                f"You can't manage **{role.name}**: it is not below your "
                "highest role."
            )

        return None

    async def log_role_action(
        self,
        interaction: discord.Interaction,
        action: str,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        assert interaction.guild is not None

        await self.bot.state.append_moderation_log(
            interaction.guild.id,
            {
                "action": action,
                "moderator_name": str(interaction.user),
                "target": f"{member} ({member.id})",
                "reason": f"role: {role.name}",
                "detail": None,
                "created_at": now_iso(),
            },
        )

    @role_group.command(name="add", description="Give a role to a member")
    @app_commands.describe(member="Member to update", role="Role to add")
    async def role_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            return

        problem = await self.check_hierarchy(interaction, role)

        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message(
                f"{member.mention} already has **{role.name}**.",
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(
                role, reason=f"/role add by {interaction.user}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I'm missing the Manage Roles permission.",
                ephemeral=True,
            )
            return

        await self.log_role_action(interaction, "role_add", member, role)
        await interaction.response.send_message(
            f"Added **{role.name}** to {member.mention}.",
            ephemeral=True,
        )

    @role_group.command(name="remove", description="Remove a role from a member")
    @app_commands.describe(member="Member to update", role="Role to remove")
    async def role_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
    ) -> None:
        if interaction.guild is None:
            return

        problem = await self.check_hierarchy(interaction, role)

        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return

        if role not in member.roles:
            await interaction.response.send_message(
                f"{member.mention} doesn't have **{role.name}**.",
                ephemeral=True,
            )
            return

        try:
            await member.remove_roles(
                role, reason=f"/role remove by {interaction.user}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I'm missing the Manage Roles permission.",
                ephemeral=True,
            )
            return

        await self.log_role_action(interaction, "role_remove", member, role)
        await interaction.response.send_message(
            f"Removed **{role.name}** from {member.mention}.",
            ephemeral=True,
        )
