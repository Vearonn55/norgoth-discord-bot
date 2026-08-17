"""Policy matrix for Image Only Channel and Link Only Channel."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from bot.automod_content import (  # noqa: E402
    is_image_only_compliant,
    is_link_only_compliant,
    is_link_only_content,
    message_has_image_attachment,
)


def _image(content_type: str = "image/png", filename: str = "a.png") -> SimpleNamespace:
    return SimpleNamespace(content_type=content_type, filename=filename)


def _msg(**kwargs: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "content": "",
        "attachments": [],
        "stickers": [],
        "poll": None,
        "embeds": [],
        "message_snapshots": None,
        "flags": SimpleNamespace(is_forwarded=False),
        "type": SimpleNamespace(name="default"),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_image_attachment_no_text() -> None:
    assert is_image_only_compliant(_msg(attachments=[_image()])) is True


def test_image_attachment_with_caption() -> None:
    assert is_image_only_compliant(
        _msg(content="look at this", attachments=[_image()])
    ) is True


def test_caption_forbidden_when_disabled() -> None:
    assert (
        is_image_only_compliant(
            _msg(content="caption", attachments=[_image()]),
            caption_allowed=False,
        )
        is False
    )


def test_text_only_rejected() -> None:
    assert is_image_only_compliant(_msg(content="hello")) is False


def test_multiple_images_allowed() -> None:
    assert is_image_only_compliant(
        _msg(attachments=[_image("image/png"), _image("image/gif", "x.gif")])
    ) is True


def test_mixed_attachments_rejected() -> None:
    assert is_image_only_compliant(
        _msg(
            attachments=[
                _image(),
                SimpleNamespace(content_type="video/mp4", filename="clip.mp4"),
            ]
        )
    ) is False


def test_missing_content_type_rejected() -> None:
    assert message_has_image_attachment(
        _msg(attachments=[SimpleNamespace(content_type=None, filename="a.png")])
    ) is False


def test_stickers_rejected() -> None:
    assert is_image_only_compliant(
        _msg(stickers=[SimpleNamespace(id=1)], attachments=[])
    ) is False


def test_gif_attachment_allowed() -> None:
    assert is_image_only_compliant(
        _msg(attachments=[_image("image/gif", "fun.gif")])
    ) is True


def test_external_image_url_rejected() -> None:
    assert is_image_only_compliant(
        _msg(content="https://example.com/cat.png")
    ) is False


def test_tenor_link_rejected_as_image() -> None:
    assert is_image_only_compliant(
        _msg(content="https://tenor.com/view/funny-gif-123")
    ) is False


def test_embed_preview_is_not_an_image() -> None:
    embed = SimpleNamespace(image=SimpleNamespace(url="https://cdn.example/x.png"))
    assert is_image_only_compliant(_msg(embeds=[embed])) is False


def test_poll_rejected() -> None:
    assert is_image_only_compliant(
        _msg(poll=SimpleNamespace(question="q"), attachments=[_image()])
    ) is False


def test_forward_without_live_image_rejected() -> None:
    assert is_image_only_compliant(
        _msg(message_snapshots=[SimpleNamespace(id=1)])
    ) is False


def test_forward_with_live_image_allowed() -> None:
    assert is_image_only_compliant(
        _msg(
            attachments=[_image()],
            message_snapshots=[SimpleNamespace(id=1)],
        )
    ) is True


def test_one_plain_url() -> None:
    assert is_link_only_content("https://example.com") is True
    assert is_link_only_compliant(_msg(content="https://example.com")) is True


def test_multiple_urls_whitespace_and_newlines() -> None:
    assert is_link_only_content("https://a.example\n  https://b.example") is True


def test_autolink_allowed() -> None:
    assert is_link_only_content("<https://example.com>") is True


def test_markdown_labelled_link_rejected() -> None:
    assert is_link_only_content("[click](https://example.com)") is False


def test_url_trailing_punctuation_allowed() -> None:
    assert is_link_only_content("https://example.com.") is True


def test_discord_invite_and_message_links_are_format_valid() -> None:
    assert is_link_only_content("https://discord.gg/abcdef") is True
    assert is_link_only_content(
        "https://discord.com/channels/1/2/3"
    ) is True


def test_mention_or_emoji_plus_url_rejected() -> None:
    assert is_link_only_content("<@123> https://example.com") is False
    assert is_link_only_content("<:wave:1> https://example.com") is False


def test_prose_plus_url_rejected() -> None:
    assert is_link_only_content("check https://example.com") is False


def test_unsafe_schemes_rejected() -> None:
    assert is_link_only_content("javascript:alert(1)") is False
    assert is_link_only_content("data:text/html,hi") is False
    assert is_link_only_content("file:///etc/passwd") is False
    assert is_link_only_content("ftp://example.com") is False


def test_credentials_in_url_rejected() -> None:
    assert is_link_only_content("https://user:pass@example.com") is False


def test_attachment_with_url_rejected() -> None:
    assert is_link_only_compliant(
        _msg(content="https://example.com", attachments=[_image()])
    ) is False


def test_embeds_ignored_for_link_only() -> None:
    embed = SimpleNamespace(url="https://example.com")
    assert is_link_only_compliant(
        _msg(content="https://example.com", embeds=[embed])
    ) is True
    assert is_link_only_compliant(_msg(content="", embeds=[embed])) is False


def test_idn_host_allowed() -> None:
    assert is_link_only_content("https://münchen.example/path") is True


def test_empty_and_whitespace_rejected() -> None:
    assert is_link_only_content("") is False
    assert is_link_only_content("   \n") is False
