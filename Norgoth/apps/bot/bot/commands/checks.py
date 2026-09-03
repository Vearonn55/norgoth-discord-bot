"""Shared slash-command checks: module gates, hierarchy, bot permissions."""

from __future__ import annotations

from typing import Callable

import discord
from discord import app_commands

from bot.commands.errors import HierarchyError, ModuleDisabledError


def module_enabled(module: str) -> Callable[[discord.Interaction], object]:
    """Require a dashboard module flag to be on for the current guild."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True

        bot = interaction.client
        state = getattr(bot, "state", None)
        if state is None:
            return True

        enabled = await state.is_module_enabled(interaction.guild.id, module)
        if not enabled:
            raise ModuleDisabledError(module)
        return True

    return app_commands.check(predicate)


def member_hierarchy_problem(
    actor: discord.Member,
    target: discord.Member,
    me: discord.Member | None,
) -> str | None:
    """Return a user-facing error if hierarchy blocks moderating ``target``."""

    guild = actor.guild
    if target.id == guild.owner_id:
        return "You can't moderate the server owner."
    if target.id == actor.id:
        return "You can't moderate yourself."
    if me is not None and target.id == me.id:
        return "I can't moderate myself."
    if me is not None and target.top_role >= me.top_role:
        return (
            "I can't moderate that member: their highest role is above or "
            "equal to mine."
        )
    if actor.id != guild.owner_id and target.top_role >= actor.top_role:
        return (
            "You can't moderate that member: their highest role is above or "
            "equal to yours."
        )
    return None


def role_hierarchy_problem(
    actor: discord.Member,
    role: discord.Role,
    me: discord.Member | None,
) -> str | None:
    """Return a user-facing error if hierarchy blocks managing ``role``."""

    guild = actor.guild
    if role.managed:
        return f"**{role.name}** is managed by an integration."
    if me is not None and role >= me.top_role:
        return f"I can't manage **{role.name}**: it is above my highest role."
    if actor.id != guild.owner_id and role >= actor.top_role:
        return (
            f"You can't manage **{role.name}**: it is not below your highest "
            "role."
        )
    return None


async def ensure_member_hierarchy(
    interaction: discord.Interaction,
    target: discord.Member,
) -> None:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        raise HierarchyError("This action only works in a server.")

    problem = member_hierarchy_problem(
        interaction.user,
        target,
        interaction.guild.me,
    )
    if problem:
        raise HierarchyError(problem)


def truncate_reason(reason: str | None, *, limit: int = 400) -> str | None:
    if reason is None:
        return None
    cleaned = reason.strip()
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


NO_MENTIONS = discord.AllowedMentions(everyone=False, users=False, roles=False)
