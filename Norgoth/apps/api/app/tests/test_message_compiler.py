"""Tests for Discord message compiler."""

from __future__ import annotations

from app.services.discord.message_compiler import compile_discord_messages


def test_compile_single_short_message() -> None:
    result = compile_discord_messages(
        content="Hello",
        embed_json={"title": "T", "description": "Body"},
    )
    assert result.ok
    assert len(result.payloads) == 1
    assert result.payloads[0]["content"] == "Hello"
    assert result.payloads[0]["embeds"][0]["title"] == "T"


def test_compile_packs_long_description_into_stacked_embeds() -> None:
    long_desc = ("Paragraph one.\n\n" * 300).strip()
    result = compile_discord_messages(embed_json={"description": long_desc})
    assert result.ok
    assert len(result.payloads) == 1
    embeds = result.payloads[0]["embeds"]
    assert len(embeds) >= 2
    restored = "\n\n".join(embed["description"] for embed in embeds)
    assert "Paragraph one." in restored
    for embed in embeds:
        assert len(embed["description"]) <= 4096


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
    assert len(result.payloads[0]["embeds"]) >= 2


def test_compile_rejects_too_many_segments() -> None:
    chunks = ["x" * 4000 for _ in range(51)]
    result = compile_discord_messages(embed_json={"description": "\n\n".join(chunks)})
    assert not result.ok
    assert result.errors[0].code == "content_too_long_for_delivery"
