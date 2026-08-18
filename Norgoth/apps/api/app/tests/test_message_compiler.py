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


def test_compile_splits_long_description() -> None:
    long_desc = ("Paragraph one.\n\n" * 300).strip()
    result = compile_discord_messages(embed_json={"description": long_desc})
    assert result.ok
    assert len(result.payloads) >= 2


def test_compile_rejects_too_many_segments() -> None:
    chunks = ["x" * 4000 for _ in range(6)]
    result = compile_discord_messages(embed_json={"description": "\n\n".join(chunks)})
    assert not result.ok
    assert result.errors[0].code == "content_too_long_for_delivery"
