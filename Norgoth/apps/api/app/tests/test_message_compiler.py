"""Tests for Discord message compiler."""

from __future__ import annotations

from app.services.discord.message_compiler import (
    _pack_embed_groups,
    compile_discord_messages,
)


def test_compile_single_short_message() -> None:
    result = compile_discord_messages(
        content="Hello",
        embed_json={"title": "T", "description": "Body"},
    )
    assert result.ok
    assert len(result.payloads) == 1
    assert result.payloads[0]["content"] == "Hello"
    assert result.payloads[0]["embeds"][0]["title"] == "T"


def _payload_embed_chars(payload: dict) -> int:
    from app.services.discord.message_compiler import _built_total_chars

    return sum(_built_total_chars(embed) for embed in payload.get("embeds") or [])


def test_compile_packs_long_description_into_stacked_embeds() -> None:
    long_desc = ("Paragraph one.\n\n" * 300).strip()
    result = compile_discord_messages(embed_json={"description": long_desc})
    assert result.ok
    embeds = [embed for payload in result.payloads for embed in payload["embeds"]]
    assert len(embeds) >= 2
    restored = "\n\n".join(embed["description"] for embed in embeds)
    assert "Paragraph one." in restored
    for embed in embeds:
        assert len(embed["description"]) <= 4096
    for payload in result.payloads:
        assert _payload_embed_chars(payload) <= 6000
        assert payload["allowed_mentions"] == {"parse": []}


def test_compile_keeps_first_embed_under_total_budget() -> None:
    result = compile_discord_messages(
        embed_json={
            "title": "T" * 256,
            "footer": "F" * 100,
            "description": "x" * 5000,
        }
    )
    assert result.ok
    first = result.payloads[0]["embeds"][0]
    total = len(str(first.get("title") or "")) + len(str(first.get("description") or ""))
    footer = first.get("footer")
    if isinstance(footer, dict):
        total += len(str(footer.get("text") or ""))
    assert total <= 6000
    all_embeds = [embed for payload in result.payloads for embed in payload["embeds"]]
    assert len(all_embeds) >= 2


def test_compile_three_large_embeds_split_across_messages() -> None:
    """Three ~4000-char cards exceed Discord's 6000-across-message cap."""
    long_desc = ("Paragraph.\n\n" * 800).strip()
    result = compile_discord_messages(embed_json={"description": long_desc})
    assert result.ok
    embeds = [embed for payload in result.payloads for embed in payload.get("embeds") or []]
    assert len(embeds) >= 3
    assert len(result.payloads) >= 2
    for payload in result.payloads:
        assert _payload_embed_chars(payload) <= 6000
        assert len(payload.get("embeds") or []) <= 10


def test_compile_three_small_embeds_stay_in_one_message() -> None:
    groups = _pack_embed_groups(
        [{"description": "a" * 1500} for _ in range(3)]
    )
    assert len(groups) == 1
    assert len(groups[0]) == 3
    assert _payload_embed_chars({"embeds": groups[0]}) <= 6000


def test_compile_rejects_too_many_segments() -> None:
    chunks = ["x" * 4000 for _ in range(51)]
    result = compile_discord_messages(embed_json={"description": "\n\n".join(chunks)})
    assert not result.ok
    assert result.errors[0].code == "content_too_long_for_delivery"
