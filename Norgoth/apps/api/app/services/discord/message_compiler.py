"""Compile authored markdown + embed JSON into Discord-safe message payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.content_limits import (
    DISCORD_MAX_CONTENT,
    DISCORD_MAX_EMBED_DESCRIPTION,
    DISCORD_MAX_MESSAGES_PER_DELIVERY,
)
from app.services.discord.embed_builder import DISCORD_LIMITS, build_embed_dict


@dataclass
class CompileError:
    code: str
    message: str


@dataclass
class CompileResult:
    payloads: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[CompileError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.payloads)


def _split_markdown(text: str, limit: int) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        return []
    if len(trimmed) <= limit:
        return [trimmed]

    chunks: list[str] = []
    remaining = trimmed

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining.strip())
            break

        window = remaining[: limit + 1]
        split_at = -1

        for marker in ("\n\n", "\n#", "\n-", "\n*", "\n1.", "\n"):
            idx = window.rfind(marker)
            if idx > limit // 4:
                split_at = idx + len(marker)
                break

        if split_at <= 0:
            split_at = limit

        candidate = remaining[:split_at].rstrip()
        if not candidate:
            candidate = remaining[:limit]
            split_at = limit

        chunks.append(candidate)
        remaining = remaining[split_at:].lstrip()

    return [chunk for chunk in chunks if chunk.strip()]


def _split_embed_description(description: str) -> list[str]:
    return _split_markdown(description, DISCORD_MAX_EMBED_DESCRIPTION)


def compile_discord_messages(
    *,
    content: str | None = None,
    embed_json: dict[str, Any] | None = None,
    fallback_name: str | None = None,
) -> CompileResult:
    """Turn stored markdown + embed into one or more Discord REST payloads."""

    result = CompileResult()
    body = (content or "").strip()
    embed_in = embed_json if isinstance(embed_json, dict) else {}

    description = embed_in.get("description")
    desc_text = description.strip() if isinstance(description, str) else ""
    title = embed_in.get("title")
    has_title = isinstance(title, str) and bool(title.strip())

    desc_parts = _split_embed_description(desc_text) if desc_text else []
    content_parts = _split_markdown(body, DISCORD_MAX_CONTENT) if body else []

    segment_count = max(len(desc_parts), len(content_parts), 1 if has_title or embed_in else 0)
    if not desc_parts and not content_parts and not has_title:
        built = build_embed_dict(embed_in)
        if built:
            result.payloads.append({"embeds": [built]})
            return result
        if fallback_name:
            result.payloads.append({"content": fallback_name[:DISCORD_MAX_CONTENT]})
            return result
        result.errors.append(
            CompileError(
                code="empty_message",
                message="Nothing to deliver.",
            )
        )
        return result

    if segment_count > DISCORD_MAX_MESSAGES_PER_DELIVERY:
        result.errors.append(
            CompileError(
                code="content_too_long_for_delivery",
                message=(
                    f"Content requires {segment_count} messages but the limit is "
                    f"{DISCORD_MAX_MESSAGES_PER_DELIVERY}."
                ),
            )
        )
        return result

    if not desc_parts:
        desc_parts = [""] * segment_count
    if not content_parts:
        content_parts = [""] * segment_count

    while len(desc_parts) < segment_count:
        desc_parts.append("")
    while len(content_parts) < segment_count:
        content_parts.append("")

    for index in range(segment_count):
        segment_embed = dict(embed_in)
        if desc_parts[index]:
            segment_embed["description"] = desc_parts[index]
        elif index > 0:
            segment_embed.pop("description", None)

        if index > 0:
            segment_embed.pop("title", None)
            segment_embed.pop("author", None)
            segment_embed.pop("thumbnail_url", None)
            segment_embed.pop("image_url", None)
            segment_embed.pop("fields", None)

        payload: dict[str, Any] = {}
        part_content = content_parts[index].strip()
        if part_content:
            payload["content"] = part_content[:DISCORD_MAX_CONTENT]

        built = build_embed_dict(segment_embed)
        if built:
            total = sum(
                len(str(built.get(key, "")))
                for key in ("title", "description")
                if isinstance(built.get(key), str)
            )
            footer = built.get("footer")
            if isinstance(footer, dict) and isinstance(footer.get("text"), str):
                total += len(footer["text"])
            author = built.get("author")
            if isinstance(author, dict) and isinstance(author.get("name"), str):
                total += len(author["name"])
            for field in built.get("fields") or []:
                if isinstance(field, dict):
                    total += len(str(field.get("name") or ""))
                    total += len(str(field.get("value") or ""))
            if total > DISCORD_LIMITS["total"]:
                result.errors.append(
                    CompileError(
                        code="embed_total_exceeded",
                        message="Embed exceeds Discord's total character limit.",
                    )
                )
                return result
            payload["embeds"] = [built]

        if payload:
            result.payloads.append(payload)

    if not result.payloads:
        result.errors.append(
            CompileError(
                code="empty_message",
                message="Nothing to deliver.",
            )
        )

    return result
