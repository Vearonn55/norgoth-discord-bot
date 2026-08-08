"""Self-assignable role menus: configuration and panel publishing."""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Literal, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.services.campaign_store import get_redis, now_iso

router = APIRouter(
    tags=["Role Menus"],
    dependencies=[Depends(guild_manager_dependency())],
)

DISCORD_API_BASE_URL = "https://discord.com/api/v10"
SNOWFLAKE_PATTERN = r"^[0-9]{5,25}$"

ROLE_MENU_PREFIX = "norgoth:rolemenu:"
MAX_ROLES_PER_MENU = 25

BUTTON_STYLES = {
    "primary": 1,
    "secondary": 2,
    "success": 3,
    "danger": 4,
}


def parse_emoji_token(raw: object) -> dict[str, Any] | None:
    """Build Discord component emoji object from stored string.

    Accepts unicode, `name:id`, `a:name:id`, or `<a?:name:id>`.
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None

    mention = re.match(r"^<(a?):([a-zA-Z0-9_]+):(\d+)>$", value)
    if mention:
        payload: dict[str, Any] = {
            "name": mention.group(2),
            "id": mention.group(3),
        }
        if mention.group(1) == "a":
            payload["animated"] = True
        return payload

    custom = re.match(r"^(a:)?([a-zA-Z0-9_]+):(\d+)$", value)
    if custom:
        payload = {"name": custom.group(2), "id": custom.group(3)}
        if custom.group(1):
            payload["animated"] = True
        return payload

    return {"name": value[:32]}


def reaction_path_segment(raw: object) -> str | None:
    """URL path segment for PUT /reactions/{emoji}/@me."""
    parsed = parse_emoji_token(raw)
    if not parsed:
        return None
    if "id" in parsed:
        return quote(f"{parsed['name']}:{parsed['id']}")
    return quote(str(parsed["name"]))


def role_menus_key(guild_id: str) -> str:
    return f"norgoth:guild:{guild_id}:rolemenus"


class RoleMenuEntry(BaseModel):
    role_id: str = Field(pattern=SNOWFLAKE_PATTERN)
    label: str = Field(min_length=1, max_length=80)
    mode: Literal["toggle", "give", "take"] = "toggle"
    style: Literal["primary", "secondary", "success", "danger"] = "secondary"
    emoji: Optional[str] = Field(default=None, max_length=100)


class RoleMenu(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    interaction: Literal["buttons", "select", "reactions"] = "buttons"
    roles: list[RoleMenuEntry] = Field(
        default_factory=list,
        max_length=MAX_ROLES_PER_MENU,
    )
    published_at: Optional[str] = None
    message_id: Optional[str] = None


class RoleMenusUpdate(BaseModel):
    menus: list[RoleMenu] = Field(default_factory=list)


async def read_menus(guild_id: str) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        raw = await redis_client.get(role_menus_key(guild_id))
    finally:
        await redis_client.aclose()

    if not raw:
        return []

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return []

    menus = stored.get("menus") if isinstance(stored, dict) else None
    return menus if isinstance(menus, list) else []


async def write_menus(guild_id: str, menus: list[dict[str, Any]]) -> None:
    redis_client = await get_redis()

    try:
        await redis_client.set(
            role_menus_key(guild_id),
            json.dumps({"menus": menus, "updated_at": now_iso()}),
        )
    finally:
        await redis_client.aclose()


@router.get("/guilds/{guild_id}/role-menus")
async def get_role_menus(guild_id: str) -> dict[str, Any]:
    return {"menus": await read_menus(guild_id)}


@router.put("/guilds/{guild_id}/role-menus")
async def update_role_menus(
    guild_id: str,
    payload: RoleMenusUpdate,
) -> dict[str, Any]:
    menus = [menu.model_dump() for menu in payload.menus]
    await write_menus(guild_id, menus)
    return {"menus": menus}


@router.delete("/guilds/{guild_id}/role-menus/{menu_id}")
async def delete_role_menu(guild_id: str, menu_id: str) -> dict[str, Any]:
    """Delete a role menu, cleaning up its published Discord message.

    If the menu was published, its live message (and thus buttons/select/
    reactions) is deleted from Discord first so no orphaned controls remain.
    A missing message (already deleted in Discord) is treated as success.
    """

    menus = await read_menus(guild_id)
    menu = next((item for item in menus if item.get("id") == menu_id), None)

    if menu is None:
        raise HTTPException(status_code=404, detail="Role menu not found.")

    discord_deleted = False
    message_id = str(menu.get("message_id") or "").strip() or None
    channel_id = str(menu.get("channel_id") or "").strip() or None

    if message_id and channel_id:
        bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        if bot_token:
            auth_headers = {"Authorization": f"Bot {bot_token}"}
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.delete(
                        (
                            f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                            f"/messages/{message_id}"
                        ),
                        headers=auth_headers,
                    )
                # 404 means the message is already gone — idempotent success.
                if response.status_code in (200, 204, 404):
                    discord_deleted = response.status_code in (200, 204)
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            f"Discord rejected the menu deletion "
                            f"(HTTP {response.status_code}): {response.text[:200]}"
                        ),
                    )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not reach Discord: {error}",
                ) from error

    remaining = [item for item in menus if item.get("id") != menu_id]
    await write_menus(guild_id, remaining)

    return {
        "ok": True,
        "deleted_id": menu_id,
        "discord_deleted": discord_deleted,
        "menus": remaining,
    }


@router.post("/guilds/{guild_id}/role-menus/{menu_id}/publish")
async def publish_role_menu(guild_id: str, menu_id: str) -> dict[str, Any]:
    """Post the role menu embed with one toggle button per role."""

    bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    if not bot_token:
        raise HTTPException(
            status_code=503,
            detail="DISCORD_BOT_TOKEN is not configured in Norgoth/.env.",
        )

    menus = await read_menus(guild_id)
    menu = next((item for item in menus if item.get("id") == menu_id), None)

    if menu is None:
        raise HTTPException(status_code=404, detail="Role menu not found.")

    if not menu.get("channel_id"):
        raise HTTPException(
            status_code=400,
            detail="The menu has no target channel configured.",
        )

    roles = menu.get("roles", [])

    if not roles:
        raise HTTPException(
            status_code=400,
            detail="Add at least one role to the menu before publishing.",
        )

    interaction = menu.get("interaction") or "buttons"
    components: list[dict[str, Any]] = []

    if interaction == "select":
        options = []
        for role in roles[:25]:
            option: dict[str, Any] = {
                "label": str(role.get("label") or role["role_id"])[:100],
                "value": f"{role.get('mode') or 'toggle'}:{role['role_id']}",
            }
            if role.get("emoji"):
                emoji_payload = parse_emoji_token(role.get("emoji"))
                if emoji_payload:
                    option["emoji"] = emoji_payload
            options.append(option)
        components = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": f"{ROLE_MENU_PREFIX}select:{menu_id}",
                        "placeholder": "Choose a role…",
                        "min_values": 1,
                        "max_values": 1,
                        "options": options,
                    }
                ],
            }
        ]
    elif interaction == "buttons":
        rows: list[dict[str, Any]] = []
        for start in range(0, len(roles), 5):
            buttons = []
            for role in roles[start : start + 5]:
                mode = role.get("mode") or "toggle"
                style = BUTTON_STYLES.get(role.get("style") or "secondary", 2)
                button: dict[str, Any] = {
                    "type": 2,
                    "style": style,
                    "label": str(role["label"])[:80],
                    "custom_id": f"{ROLE_MENU_PREFIX}{mode}:{role['role_id']}",
                }
                if role.get("emoji"):
                    emoji_payload = parse_emoji_token(role.get("emoji"))
                    if emoji_payload:
                        button["emoji"] = emoji_payload
                buttons.append(button)
            rows.append({"type": 1, "components": buttons})
        components = rows
    else:
        # reactions: publish embed only; bot will add reactions after
        components = []

    message_payload: dict[str, Any] = {
        "embeds": [
            {
                "title": menu["title"],
                "description": menu.get("description")
                or "Choose a role from the controls below.",
                "color": 0x5865F2,
            }
        ],
        # Always send components so an edit that removed items clears stale
        # buttons/select options from the live message.
        "components": components,
    }

    auth_headers = {"Authorization": f"Bot {bot_token}"}
    channel_id = menu["channel_id"]
    existing_message_id = str(menu.get("message_id") or "").strip() or None
    edited_existing = False

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Prefer editing the previously published message so deletions and
        # edits sync to the live menu instead of spawning duplicates.
        if existing_message_id:
            try:
                edit_response = await client.patch(
                    (
                        f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                        f"/messages/{existing_message_id}"
                    ),
                    headers=auth_headers,
                    json=message_payload,
                )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not reach Discord: {error}",
                ) from error

            if edit_response.status_code == 200:
                response = edit_response
                edited_existing = True
            elif edit_response.status_code == 404:
                # Message was deleted on Discord; fall through to re-post.
                existing_message_id = None
                response = None
            else:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Discord rejected the role menu edit "
                        f"(HTTP {edit_response.status_code}): "
                        f"{edit_response.text[:200]}"
                    ),
                )
        else:
            response = None

        if response is None:
            try:
                response = await client.post(
                    f"{DISCORD_API_BASE_URL}/channels/{channel_id}/messages",
                    headers=auth_headers,
                    json=message_payload,
                )
            except httpx.HTTPError as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not reach Discord: {error}",
                ) from error

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Discord rejected the role menu "
                        f"(HTTP {response.status_code}): {response.text[:200]}"
                    ),
                )

    message_body = response.json()
    menu["published_at"] = now_iso()
    menu["message_id"] = str(message_body.get("id") or "") or None

    if interaction == "reactions" and menu.get("message_id"):
        # On edit, clear existing reactions first so removed items' reactions
        # disappear, then (re)add the current set.
        if edited_existing:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.delete(
                        (
                            f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                            f"/messages/{menu['message_id']}/reactions"
                        ),
                        headers=auth_headers,
                    )
            except httpx.HTTPError:
                pass

        for role in roles:
            segment = reaction_path_segment(role.get("emoji"))
            if not segment:
                continue
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.put(
                        (
                            f"{DISCORD_API_BASE_URL}/channels/"
                            f"{channel_id}/messages/{menu['message_id']}"
                            f"/reactions/{segment}/@me"
                        ),
                        headers=auth_headers,
                    )
            except httpx.HTTPError:
                pass

    await write_menus(guild_id, menus)

    return {
        "ok": True,
        "channel_id": menu["channel_id"],
        "published_at": menu["published_at"],
        "message_id": menu.get("message_id"),
        "interaction": interaction,
    }
