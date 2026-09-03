"""Tree-level application command error handling."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from bot.commands.i18n import t

logger = logging.getLogger("norgoth.bot.commands.errors")


class ModuleDisabledError(app_commands.CheckFailure):
    def __init__(self, module: str) -> None:
        self.module = module
        super().__init__(f"Module {module} is disabled")


class HierarchyError(app_commands.CheckFailure):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


async def _reply(interaction: discord.Interaction, content: str) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
        else:
            await interaction.response.send_message(content, ephemeral=True)
    except discord.HTTPException:
        logger.debug("Failed to send command error reply", exc_info=True)


def install_tree_error_handler(tree: app_commands.CommandTree) -> None:
    @tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        locale = getattr(interaction, "locale", None)

        if isinstance(error, ModuleDisabledError):
            await _reply(
                interaction,
                t(
                    "errors.module_disabled",
                    locale,
                    module=error.module,
                ),
            )
            return

        if isinstance(error, HierarchyError):
            await _reply(interaction, error.message)
            return

        if isinstance(error, app_commands.MissingPermissions):
            await _reply(interaction, t("errors.missing_permissions", locale))
            return

        if isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(sorted(error.missing_permissions))
            await _reply(
                interaction,
                t("errors.bot_missing_permissions", locale, permissions=missing),
            )
            return

        if isinstance(error, app_commands.CommandOnCooldown):
            await _reply(
                interaction,
                t(
                    "errors.on_cooldown",
                    locale,
                    seconds=f"{error.retry_after:.0f}",
                ),
            )
            return

        if isinstance(error, app_commands.NoPrivateMessage):
            await _reply(interaction, t("errors.guild_only", locale))
            return

        if isinstance(error, app_commands.CheckFailure):
            await _reply(interaction, t("errors.check_failed", locale))
            return

        logger.exception(
            "Unhandled app command error command=%s",
            getattr(interaction.command, "qualified_name", None),
        )
        await _reply(interaction, t("errors.unexpected", locale))
