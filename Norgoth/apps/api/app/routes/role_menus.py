"""Self-assignable role menus: configuration and panel publishing."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Literal, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies_auth import guild_manager_dependency
from app.core.content_limits import MAX_STORED_MARKDOWN_CHARS
from app.db.session import get_database_session
from app.models.embed_messages import EmbedMessageDelivery
from app.services.campaign_store import get_redis, now_iso
from app.services.feature_config_store import read_raw, save_config

logger = logging.getLogger(__name__)

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
    # Title/description are legacy standalone-embed authoring fields. New role
    # menus bind to an existing Embed Message published instance and no longer
    # author their own embed; these remain optional for backward compatibility
    # with menus created before the binding model.
    title: str = Field(default="", max_length=256)
    description: str = Field(default="", max_length=2000)
    channel_id: Optional[str] = Field(default=None, pattern=SNOWFLAKE_PATTERN)
    interaction: Literal["buttons", "select", "reactions"] = "buttons"
    roles: list[RoleMenuEntry] = Field(
        default_factory=list,
        max_length=MAX_ROLES_PER_MENU,
    )
    # Binding model: "embed_message" attaches role controls to a specific
    # published instance of an Embed Message (the content source of truth);
    # "standalone" posts/edits a bot-owned message (text or legacy embed).
    binding_type: Literal["embed_message", "standalone"] = "standalone"
    # text = RichMessageEditor body on a standalone message; embed = bind to
    # Embed Library / Select From Draft.
    message_source: Literal["text", "embed"] = "embed"
    text_content: str = Field(default="", max_length=MAX_STORED_MARKDOWN_CHARS)
    embed_message_id: Optional[str] = None
    embed_delivery_id: Optional[str] = None
    published_at: Optional[str] = None
    message_id: Optional[str] = None


class RoleMenusUpdate(BaseModel):
    menus: list[RoleMenu] = Field(default_factory=list)


async def read_menus(guild_id: str) -> list[dict[str, Any]]:
    redis_client = await get_redis()

    try:
        raw = await read_raw(guild_id, "rolemenus", redis_client)
    finally:
        await redis_client.aclose()

    if not raw:
        return []

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        return []

    menus = stored.get("menus") if isinstance(stored, dict) else None
    if not isinstance(menus, list):
        return []

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        if menu.get("message_source") not in ("text", "embed"):
            if menu.get("binding_type") == "embed_message" or menu.get(
                "embed_message_id"
            ):
                menu["message_source"] = "embed"
            elif menu.get("text_content") or menu.get("title") or menu.get(
                "description"
            ):
                menu["message_source"] = "text"
                if not menu.get("text_content"):
                    desc = str(menu.get("description") or "").strip()
                    title = str(menu.get("title") or "").strip()
                    menu["text_content"] = desc or title
            else:
                menu["message_source"] = "embed"
        if "text_content" not in menu:
            menu["text_content"] = ""

    return menus


async def write_menus(guild_id: str, menus: list[dict[str, Any]]) -> None:
    await save_config(
        guild_id,
        "rolemenus",
        {"menus": menus, "updated_at": now_iso()},
        enabled=True,
    )


def build_role_components(
    menu_id: str,
    interaction: str,
    roles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build Discord message components for a role menu's interaction type.

    Returns an empty list for the ``reactions`` interaction (reactions are
    applied separately, not as message components).
    """

    if interaction == "select":
        options: list[dict[str, Any]] = []
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
        return [
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

    if interaction == "buttons":
        rows: list[dict[str, Any]] = []
        for start in range(0, len(roles), 5):
            buttons: list[dict[str, Any]] = []
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
        return rows

    # reactions: no message components; bot adds reactions after publish.
    return []


async def _resolve_embed_binding(
    session: AsyncSession,
    guild_id: str,
    menu: dict[str, Any],
) -> EmbedMessageDelivery:
    """Resolve the Embed Message delivery a role menu is bound to.

    Raises 400/404 with actionable messages when the binding is incomplete or
    the embed instance has not been published to Discord yet.
    """

    delivery_id = str(menu.get("embed_delivery_id") or "").strip()
    if not delivery_id:
        raise HTTPException(
            status_code=400,
            detail="Select an Embed Message template for this menu.",
        )

    try:
        delivery_uuid = uuid.UUID(delivery_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid Embed Message instance reference.",
        ) from error

    delivery = await session.scalar(
        select(EmbedMessageDelivery).where(
            EmbedMessageDelivery.id == delivery_uuid,
            EmbedMessageDelivery.guild_id == guild_id,
        )
    )

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The bound Embed Message instance no longer exists. "
                "Re-select a published instance."
            ),
        )

    if not delivery.discord_message_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "The bound Embed Message has not been posted yet. "
                "Save the menu to post a new Discord message."
            ),
        )

    return delivery


async def apply_role_menu_components(
    *,
    bot_token: str,
    channel_id: str,
    message_id: str,
    interaction: str,
    components: list[dict[str, Any]],
    roles: list[dict[str, Any]],
    clear_existing_reactions: bool = True,
) -> None:
    """PATCH role controls onto an existing Discord message.

    Used when a menu is bound to an Embed Message instance: we attach/replace
    only the ``components`` (and reactions for the reactions interaction) and
    never touch the embed content, which the Embed Message owns.
    """

    auth_headers = {"Authorization": f"Bot {bot_token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.patch(
            (
                f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                f"/messages/{message_id}"
            ),
            headers=auth_headers,
            json={"components": components},
        )
        if response.status_code == 404:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The bound Discord message is missing. Re-sync the Embed "
                    "Message or re-select a published instance."
                ),
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Discord rejected the role controls "
                    f"(HTTP {response.status_code}): {response.text[:200]}"
                ),
            )

    if interaction != "reactions":
        return

    if clear_existing_reactions:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(
                    (
                        f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                        f"/messages/{message_id}/reactions"
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
                        f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                        f"/messages/{message_id}/reactions/{segment}/@me"
                    ),
                    headers=auth_headers,
                )
        except httpx.HTTPError:
            pass


async def compute_binding_health(
    session: AsyncSession,
    guild_id: str,
    menus: list[dict[str, Any]],
) -> None:
    """Annotate each menu with a ``binding_health`` field in place.

    Health states for embed-bound menus:
      - ``healthy``: the bound instance exists and its live message matches.
      - ``needs_resync``: the instance's Discord message id drifted (e.g. the
        Embed Message was re-sent) — components must be re-applied.
      - ``message_missing``: the instance exists but is not live in Discord.
      - ``needs_reassignment``: the bound instance no longer exists.
      - ``unbound``: no instance is selected yet.
    Standalone menus report ``standalone``.
    """

    delivery_ids: set[uuid.UUID] = set()
    for menu in menus:
        if menu.get("binding_type") != "embed_message":
            continue
        raw_id = str(menu.get("embed_delivery_id") or "").strip()
        if not raw_id:
            continue
        try:
            delivery_ids.add(uuid.UUID(raw_id))
        except ValueError:
            continue

    deliveries: dict[str, EmbedMessageDelivery] = {}
    if delivery_ids:
        rows = await session.scalars(
            select(EmbedMessageDelivery).where(
                EmbedMessageDelivery.guild_id == guild_id,
                EmbedMessageDelivery.id.in_(delivery_ids),
            )
        )
        deliveries = {str(row.id): row for row in rows}

    for menu in menus:
        if menu.get("binding_type") != "embed_message":
            menu["binding_health"] = "standalone"
            continue

        delivery_id = str(menu.get("embed_delivery_id") or "").strip()
        if not delivery_id:
            menu["binding_health"] = "unbound"
            continue

        delivery = deliveries.get(delivery_id)
        if delivery is None:
            menu["binding_health"] = "needs_reassignment"
        elif not delivery.discord_message_id:
            menu["binding_health"] = "message_missing"
        elif str(delivery.discord_message_id) != str(menu.get("message_id") or ""):
            menu["binding_health"] = "needs_resync"
        elif menu.get("components_stale"):
            # A prior component re-apply failed after the message was recreated.
            menu["binding_health"] = "needs_resync"
        else:
            menu["binding_health"] = "healthy"


async def reapply_menu_components_for_deliveries(
    guild_id: str,
    changed: dict[str, tuple[str, str]],
    bot_token: str,
) -> None:
    """Re-apply role controls to bound menus after their instance was re-sent.

    ``changed`` maps ``embed_delivery_id`` → ``(channel_id, discord_message_id)``
    for deliveries whose Discord message id changed during an embed re-sync.
    Editing an embed's content keeps its components, so this only needs to run
    when the underlying message was recreated (new id).
    """

    if not changed:
        return

    menus = await read_menus(guild_id)
    dirty = False

    for menu in menus:
        if menu.get("binding_type") != "embed_message":
            continue
        delivery_id = str(menu.get("embed_delivery_id") or "").strip()
        if delivery_id not in changed:
            continue
        roles = menu.get("roles") or []
        if not roles:
            continue

        channel_id, message_id = changed[delivery_id]
        interaction = menu.get("interaction") or "buttons"
        components = build_role_components(str(menu["id"]), interaction, roles)
        try:
            await apply_role_menu_components(
                bot_token=bot_token,
                channel_id=channel_id,
                message_id=message_id,
                interaction=interaction,
                components=components,
                roles=roles,
            )
        except HTTPException as error:
            # The message was recreated but its role controls could not be
            # re-applied. Persist a marker so binding_health flags the menu as
            # needing a re-sync instead of silently losing its controls.
            logger.warning(
                "Failed to re-apply role components for menu %s on message %s: %s",
                menu.get("id"),
                message_id,
                getattr(error, "detail", error),
            )
            menu["components_stale"] = True
            dirty = True
            continue

        menu["channel_id"] = channel_id
        menu["message_id"] = message_id
        menu["published_at"] = now_iso()
        menu["components_stale"] = False
        dirty = True

    if dirty:
        await write_menus(guild_id, menus)


@router.get("/guilds/{guild_id}/role-menus")
async def get_role_menus(
    guild_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    menus = await read_menus(guild_id)
    await compute_binding_health(session, guild_id, menus)
    return {"menus": menus}


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
    binding_type = menu.get("binding_type") or "standalone"

    if message_id and channel_id:
        bot_token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        if bot_token:
            auth_headers = {"Authorization": f"Bot {bot_token}"}
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    if binding_type == "embed_message":
                        # The message belongs to an Embed Message instance — do
                        # NOT delete it. Strip only the role controls we added.
                        response = await client.patch(
                            (
                                f"{DISCORD_API_BASE_URL}/channels/{channel_id}"
                                f"/messages/{message_id}"
                            ),
                            headers=auth_headers,
                            json={"components": []},
                        )
                        if menu.get("interaction") == "reactions":
                            try:
                                await client.delete(
                                    (
                                        f"{DISCORD_API_BASE_URL}/channels/"
                                        f"{channel_id}/messages/{message_id}"
                                        f"/reactions"
                                    ),
                                    headers=auth_headers,
                                )
                            except httpx.HTTPError:
                                pass
                    else:
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
async def publish_role_menu(
    guild_id: str,
    menu_id: str,
    session: AsyncSession = Depends(get_database_session),
) -> dict[str, Any]:
    """Publish a role menu's controls.

    For ``embed_message`` bindings the controls are attached (PATCH) to the
    exact selected published Embed Message instance without touching its
    content. For legacy ``standalone`` menus a self-authored embed is posted or
    edited.
    """

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

    roles = menu.get("roles", [])

    if not roles:
        raise HTTPException(
            status_code=400,
            detail="Add at least one role to the menu before publishing.",
        )

    interaction = menu.get("interaction") or "buttons"
    binding_type = menu.get("binding_type") or "standalone"
    message_source = menu.get("message_source") or (
        "embed" if binding_type == "embed_message" else "text"
    )

    if message_source == "embed" and binding_type == "embed_message":
        delivery = await _resolve_embed_binding(session, guild_id, menu)
        # Record that this deployment is owned by Self-Assignable Roles so the
        # Embed Library's generic Re-Sync never recreates it as a plain embed
        # (it needs role components). Runtime binding detection is authoritative
        # too, but stamping keeps the column accurate.
        if delivery.owner_feature != "self_assignable_role":
            delivery.owner_feature = "self_assignable_role"
            await session.commit()
        components = build_role_components(menu_id, interaction, roles)
        await apply_role_menu_components(
            bot_token=bot_token,
            channel_id=delivery.channel_id,
            message_id=str(delivery.discord_message_id),
            interaction=interaction,
            components=components,
            roles=roles,
        )
        menu["channel_id"] = delivery.channel_id
        menu["message_id"] = str(delivery.discord_message_id)
        menu["published_at"] = now_iso()
        await write_menus(guild_id, menus)
        return {
            "ok": True,
            "channel_id": menu["channel_id"],
            "published_at": menu["published_at"],
            "message_id": menu.get("message_id"),
            "interaction": interaction,
            "binding_type": binding_type,
            "message_source": message_source,
            "embed_delivery_id": menu.get("embed_delivery_id"),
        }

    # --- Standalone path (plain text or legacy self-authored embed) ---
    if not menu.get("channel_id"):
        raise HTTPException(
            status_code=400,
            detail="The menu has no target channel configured.",
        )

    components = build_role_components(menu_id, interaction, roles)

    message_payload: dict[str, Any] = {
        # Always send components so an edit that removed items clears stale
        # buttons/select options from the live message.
        "components": components,
    }

    if message_source == "text":
        text_body = str(menu.get("text_content") or "").strip()
        if not text_body:
            text_body = (
                str(menu.get("description") or "").strip()
                or str(menu.get("title") or "").strip()
                or "Choose a role from the controls below."
            )
        message_payload["content"] = text_body[:2000]
        message_payload["embeds"] = []
    else:
        message_payload["embeds"] = [
            {
                "title": menu.get("title") or "Choose your roles",
                "description": menu.get("description")
                or "Choose a role from the controls below.",
                "color": 0x5865F2,
            }
        ]

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
