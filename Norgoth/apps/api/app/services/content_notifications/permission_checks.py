"""Permission checks for content notification destination channels."""

from __future__ import annotations

from typing import Any

# Discord permission bits
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
MANAGE_MESSAGES = 1 << 13
EMBED_LINKS = 1 << 14
MENTION_EVERYONE = 1 << 17
MANAGE_WEBHOOKS = 1 << 29


REQUIRED_BASE = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS | MANAGE_WEBHOOKS


def missing_permission_names(bits: int, *, need_mention: bool = False) -> list[str]:
    required = [
        (VIEW_CHANNEL, "View Channel"),
        (SEND_MESSAGES, "Send Messages"),
        (EMBED_LINKS, "Embed Links"),
        (MANAGE_WEBHOOKS, "Manage Webhooks"),
    ]
    if need_mention:
        required.append((MENTION_EVERYONE, "Mention Everyone / Roles"))

    missing: list[str] = []
    for flag, name in required:
        if bits & flag == 0:
            missing.append(name)
    return missing


def explain_permission_gap(
    bot_permissions: int | str | None,
    *,
    need_mention: bool = False,
) -> dict[str, Any]:
    try:
        bits = int(bot_permissions or 0)
    except (TypeError, ValueError):
        bits = 0
    missing = missing_permission_names(bits, need_mention=need_mention)
    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "permissions": bits,
    }
