"""Discord publishing for RSS feed items."""

from __future__ import annotations

from typing import Any

from app.integrations.discord.bot_rest import DiscordBotClient
from app.services.discord.embed_builder import build_embed_dict
from app.services.rss.parser import FeedItem


def build_rss_message_payload(
    item: FeedItem,
    *,
    feed_title: str | None,
    mention_role_id: str | None = None,
) -> dict[str, Any]:
    author_name = (feed_title or item.author or "RSS").strip()[:256]
    embed_def: dict[str, Any] = {
        "title": item.title,
        "description": item.summary_text or None,
        "color": "#5865F2",
        "author": {"name": author_name},
        "footer": "RSS Feed",
    }

    embed = build_embed_dict(embed_def)
    if embed is None:
        embed = {"title": item.title[:256]}
    if item.link:
        embed["url"] = item.link
    if item.published is not None:
        embed["timestamp"] = item.published.astimezone().isoformat()

    payload: dict[str, Any] = {"embeds": [embed]}
    if mention_role_id and mention_role_id.isdigit():
        payload["content"] = f"<@&{mention_role_id}>"
        payload["allowed_mentions"] = {"parse": [], "roles": [mention_role_id]}
    return payload


async def publish_item(
    bot: DiscordBotClient,
    *,
    channel_id: str,
    item: FeedItem,
    feed_title: str | None,
    mention_role_id: str | None,
) -> str | None:
    """Send embed to Discord; return message id when present."""

    payload = build_rss_message_payload(
        item,
        feed_title=feed_title,
        mention_role_id=mention_role_id,
    )
    result = await bot.send_channel_message(channel_id, payload)
    message_id = result.get("id") if isinstance(result, dict) else None
    return str(message_id) if message_id else None
