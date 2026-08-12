"""Discord CDN URL helpers."""

from __future__ import annotations

DISCORD_CDN_BASE = "https://cdn.discordapp.com"


def discord_icon_url(
    guild_id: str,
    icon_hash: str | None,
    size: int = 128,
) -> str | None:
    """Build a guild icon CDN URL. Animated hashes (``a_``) use GIF."""

    if not guild_id or not icon_hash:
        return None
    ext = "gif" if icon_hash.startswith("a_") else "png"
    return f"{DISCORD_CDN_BASE}/icons/{guild_id}/{icon_hash}.{ext}?size={size}"
