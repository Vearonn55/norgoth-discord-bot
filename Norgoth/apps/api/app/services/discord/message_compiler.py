"""Compile authored markdown + embed JSON into Discord-safe message payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.content_limits import (
    DISCORD_MAX_CONTENT,
    DISCORD_MAX_EMBED_DESCRIPTION,
    DISCORD_MAX_EMBED_FIELDS,
    DISCORD_MAX_EMBED_FOOTER,
    DISCORD_MAX_EMBED_TITLE,
    DISCORD_MAX_EMBED_TOTAL,
    DISCORD_MAX_EMBEDS_PER_MESSAGE,
    DISCORD_MAX_FIELD_NAME,
    DISCORD_MAX_FIELD_VALUE,
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


def _capped_len(value: Any, cap: int) -> int:
    if isinstance(value, str) and value.strip():
        return min(len(value.strip()), cap)
    return 0


def _fields_chars(fields: Any) -> int:
    if not isinstance(fields, list):
        return 0
    total = 0
    for raw in fields[:DISCORD_MAX_EMBED_FIELDS]:
        if not isinstance(raw, dict):
            continue
        total += min(len(str(raw.get("name") or "")), DISCORD_MAX_FIELD_NAME)
        total += min(len(str(raw.get("value") or "")), DISCORD_MAX_FIELD_VALUE)
    return total


def _author_chars(author: Any) -> int:
    if not isinstance(author, dict):
        return 0
    return _capped_len(author.get("name"), DISCORD_LIMITS["author_name"])


def _chrome_chars(
    embed_in: dict[str, Any],
    *,
    include_title: bool,
    include_author: bool,
    include_fields: bool,
    include_footer: bool,
) -> int:
    total = 0
    if include_title:
        total += _capped_len(embed_in.get("title"), DISCORD_MAX_EMBED_TITLE)
    if include_author:
        total += _author_chars(embed_in.get("author"))
    if include_fields:
        total += _fields_chars(embed_in.get("fields"))
    if include_footer:
        total += _capped_len(embed_in.get("footer"), DISCORD_MAX_EMBED_FOOTER)
    return total


def _split_markdown(text: str, limit: int, *, first_limit: int | None = None) -> list[str]:
    trimmed = text.strip()
    if not trimmed:
        return []
    if first_limit is None and len(trimmed) <= limit:
        return [trimmed]

    chunks: list[str] = []
    remaining = trimmed
    current_limit = first_limit if first_limit is not None else limit

    while remaining:
        this_limit = current_limit
        current_limit = limit
        if this_limit <= 0:
            this_limit = limit
        if len(remaining) <= this_limit:
            chunks.append(remaining.strip())
            break

        window = remaining[: this_limit + 1]
        split_at = -1

        for marker in ("\n\n", "\n#", "\n-", "\n*", "\n1.", "\n"):
            idx = window.rfind(marker)
            if idx > this_limit // 4:
                split_at = idx + len(marker)
                break

        if split_at <= 0:
            split_at = this_limit

        candidate = remaining[:split_at].rstrip()
        if not candidate:
            candidate = remaining[:this_limit]
            split_at = this_limit

        chunks.append(candidate)
        remaining = remaining[split_at:].lstrip()

    return [chunk for chunk in chunks if chunk.strip()]


def _split_embed_description(description: str, first_limit: int) -> list[str]:
    return _split_markdown(
        description,
        DISCORD_MAX_EMBED_DESCRIPTION,
        first_limit=max(first_limit, 0),
    )


def compile_discord_messages(
    *,
    content: str | None = None,
    embed_json: dict[str, Any] | None = None,
    fallback_name: str | None = None,
) -> CompileResult:
    """Turn stored markdown + embed into one or more Discord REST payloads.

    Long descriptions are split across stacked embeds (up to 10 per message)
    so community-rules posts can exceed a single 4096/6000 embed without
    truncating or failing compile.
    """

    result = CompileResult()
    body = (content or "").strip()
    embed_in = embed_json if isinstance(embed_json, dict) else {}

    description = embed_in.get("description")
    desc_text = description.strip() if isinstance(description, str) else ""
    title = embed_in.get("title")
    has_title = isinstance(title, str) and bool(title.strip())
    has_chrome = bool(
        has_title
        or _author_chars(embed_in.get("author"))
        or _fields_chars(embed_in.get("fields"))
        or _capped_len(embed_in.get("footer"), DISCORD_MAX_EMBED_FOOTER)
        or (isinstance(embed_in.get("thumbnail_url"), str) and embed_in.get("thumbnail_url", "").strip())
        or (isinstance(embed_in.get("image_url"), str) and embed_in.get("image_url", "").strip())
    )

    first_chrome = _chrome_chars(
        embed_in,
        include_title=True,
        include_author=True,
        include_fields=True,
        include_footer=False,
    )
    footer_chars = _capped_len(embed_in.get("footer"), DISCORD_MAX_EMBED_FOOTER)
    first_desc_budget = min(
        DISCORD_MAX_EMBED_DESCRIPTION,
        max(0, DISCORD_MAX_EMBED_TOTAL - first_chrome),
    )

    desc_parts = (
        _split_embed_description(desc_text, first_desc_budget) if desc_text else []
    )
    if (
        desc_parts
        and footer_chars
        and first_chrome + len(desc_parts[0]) + footer_chars > DISCORD_MAX_EMBED_TOTAL
        and len(desc_parts) == 1
    ):
        # Footer does not fit beside a maxed-out first description — continue.
        tighter = max(0, DISCORD_MAX_EMBED_TOTAL - first_chrome)
        desc_parts = _split_embed_description(desc_text, tighter)

    content_parts = _split_markdown(body, DISCORD_MAX_CONTENT) if body else []

    if not desc_parts and not content_parts and not has_chrome:
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

    embed_dicts: list[dict[str, Any]] = []
    if desc_parts or has_chrome:
        last_index = max(len(desc_parts) - 1, 0)
        for index in range(max(len(desc_parts), 1 if has_chrome else 0)):
            part_desc = desc_parts[index] if index < len(desc_parts) else ""
            is_first = index == 0
            is_last = index == last_index or (not desc_parts and is_first)
            segment = dict(embed_in)
            if part_desc:
                segment["description"] = part_desc
            else:
                segment.pop("description", None)
            if not is_first:
                segment.pop("title", None)
                segment.pop("author", None)
                segment.pop("thumbnail_url", None)
                segment.pop("image_url", None)
                segment.pop("fields", None)
            if not is_last:
                segment.pop("footer", None)
                segment.pop("footer_icon_url", None)
            built = build_embed_dict(segment)
            if not built:
                continue
            total = _built_total_chars(built)
            if total > DISCORD_MAX_EMBED_TOTAL:
                result.errors.append(
                    CompileError(
                        code="embed_total_exceeded",
                        message="Embed exceeds Discord's total character limit.",
                    )
                )
                return result
            embed_dicts.append(built)

    if not content_parts:
        content_parts = [""]
    while len(content_parts) > 1 and not content_parts[-1]:
        content_parts.pop()

    embed_groups: list[list[dict[str, Any]]] = []
    if embed_dicts:
        for start in range(0, len(embed_dicts), DISCORD_MAX_EMBEDS_PER_MESSAGE):
            embed_groups.append(embed_dicts[start : start + DISCORD_MAX_EMBEDS_PER_MESSAGE])
    else:
        embed_groups = [[]]

    segment_count = max(len(content_parts), len(embed_groups), 1)
    while len(content_parts) < segment_count:
        content_parts.append("")
    while len(embed_groups) < segment_count:
        embed_groups.append([])

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

    for index in range(segment_count):
        payload: dict[str, Any] = {}
        part_content = content_parts[index].strip()
        if part_content:
            payload["content"] = part_content[:DISCORD_MAX_CONTENT]
        group = embed_groups[index]
        if group:
            payload["embeds"] = group
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


def _built_total_chars(built: dict[str, Any]) -> int:
    total = 0
    for key in ("title", "description"):
        value = built.get(key)
        if isinstance(value, str):
            total += len(value)
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
    return total
