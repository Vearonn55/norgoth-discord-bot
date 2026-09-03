"""Shared Discord application-command infrastructure."""

from bot.commands.registry import COMMAND_MANIFEST_VERSION, COMMANDS, CommandSpec

__all__ = ["COMMAND_MANIFEST_VERSION", "COMMANDS", "CommandSpec"]
