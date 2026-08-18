"""Shared limits for stored rich-text / markdown content."""

from __future__ import annotations

# Authoring storage cap for TinyMCE-backed markdown fields (PostgreSQL Text).
MAX_STORED_MARKDOWN_CHARS = 100_000

# Discord platform limits (compile/delivery time only).
DISCORD_MAX_CONTENT = 2000
DISCORD_MAX_EMBED_DESCRIPTION = 4096
DISCORD_MAX_EMBED_TITLE = 256
DISCORD_MAX_EMBED_FOOTER = 2048
DISCORD_MAX_FIELD_NAME = 256
DISCORD_MAX_FIELD_VALUE = 1024
DISCORD_MAX_EMBED_FIELDS = 25
DISCORD_MAX_EMBED_TOTAL = 6000
DISCORD_MAX_EMBEDS_PER_MESSAGE = 10
DISCORD_MAX_MESSAGES_PER_DELIVERY = 5
