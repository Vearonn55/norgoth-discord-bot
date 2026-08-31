"""Resolve banned-account identities for manual-review evidence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.integrations.discord.bot_rest import DiscordBotClient
from app.models.guild_active_ban import GuildActiveBan
from app.schemas.review_evidence import BannedAccountEvidence
from app.services.campaign_store import get_redis
from app.services.verification_i18n import unavailable_discord_user_label

logger = logging.getLogger(__name__)

_USER_CACHE_TTL_SECONDS = 3600


def _guild_members_key(discord_guild_id: str) -> str:
    return f"norgoth:guild:{discord_guild_id}:members"


def _user_cache_key(discord_user_id: str) -> str:
    return f"norgoth:discord:user:{discord_user_id}"


async def _read_member_snapshot(
    *,
    discord_guild_id: str,
    discord_user_id: str,
) -> dict[str, str | None]:
    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001
        return {}
    try:
        raw_members = await redis_client.get(_guild_members_key(discord_guild_id))
    except Exception:  # noqa: BLE001
        return {}
    finally:
        await redis_client.aclose()

    if not raw_members:
        return {}
    try:
        snapshot = json.loads(raw_members)
    except (json.JSONDecodeError, TypeError):
        return {}

    for member in snapshot.get("members", []):
        if str(member.get("id")) != discord_user_id:
            continue
        display_name = (
            member.get("display_name")
            or member.get("global_name")
            or member.get("name")
        )
        return {
            "display_name": str(display_name) if display_name else None,
            "username": str(member.get("name")) if member.get("name") else None,
        }
    return {}


async def _read_user_cache(discord_user_id: str) -> dict[str, str | None]:
    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001
        return {}
    try:
        raw = await redis_client.get(_user_cache_key(discord_user_id))
    except Exception:  # noqa: BLE001
        return {}
    finally:
        await redis_client.aclose()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        "display_name": payload.get("display_name"),
        "username": payload.get("username"),
    }


async def _write_user_cache(
    *,
    discord_user_id: str,
    display_name: str | None,
    username: str | None,
) -> None:
    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001
        return
    try:
        await redis_client.set(
            _user_cache_key(discord_user_id),
            json.dumps(
                {
                    "display_name": display_name,
                    "username": username,
                }
            ),
            ex=_USER_CACHE_TTL_SECONDS,
        )
    except Exception:  # noqa: BLE001
        logger.debug("discord user cache write failed user_id=%s", discord_user_id)
    finally:
        await redis_client.aclose()


async def _fetch_discord_user(
    *,
    bot_client: DiscordBotClient,
    discord_user_id: str,
) -> dict[str, str | None]:
    cached = await _read_user_cache(discord_user_id)
    if cached.get("username") or cached.get("display_name"):
        return cached
    try:
        payload = await bot_client.get_user(discord_user_id)
    except Exception:  # noqa: BLE001
        return {}
    username = payload.get("username")
    display_name = payload.get("global_name") or username
    result = {
        "display_name": str(display_name) if display_name else None,
        "username": str(username) if username else None,
    }
    await _write_user_cache(
        discord_user_id=discord_user_id,
        display_name=result["display_name"],
        username=result["username"],
    )
    return result


async def resolve_banned_account_identities(
    *,
    discord_guild_id: str,
    matched_user_ids: list[str],
    ban_snapshots: dict[str, GuildActiveBan],
    bot_client: DiscordBotClient | None = None,
    lang: str = "en",
) -> list[BannedAccountEvidence]:
    """Resolve moderator-facing identities for matched banned accounts."""

    resolved_at = datetime.now(timezone.utc)
    accounts: list[BannedAccountEvidence] = []

    for user_id in matched_user_ids:
        snapshot = ban_snapshots.get(user_id)
        display_name = snapshot.display_name_snapshot if snapshot else None
        username = snapshot.username_snapshot if snapshot else None
        source = "ban_snapshot" if snapshot is not None else "unknown"

        if not display_name and not username:
            member = await _read_member_snapshot(
                discord_guild_id=discord_guild_id,
                discord_user_id=user_id,
            )
            display_name = member.get("display_name") or display_name
            username = member.get("username") or username
            if member:
                source = "member_snapshot"

        if bot_client is not None and not username:
            remote = await _fetch_discord_user(
                bot_client=bot_client,
                discord_user_id=user_id,
            )
            display_name = remote.get("display_name") or display_name
            username = remote.get("username") or username
            if remote:
                source = "discord_api"

        if not display_name and not username:
            display_name = unavailable_discord_user_label(lang=lang, user_id=user_id)
            source = "fallback"

        accounts.append(
            BannedAccountEvidence(
                discord_user_id=user_id,
                display_name=display_name,
                username=username,
                source=source,
                resolved_at=resolved_at,
            )
        )

    return accounts
