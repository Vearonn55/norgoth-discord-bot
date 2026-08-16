"""Link Embeds API config helpers — host allowlist + platform defaults."""

from __future__ import annotations

from app.routes.rich_link_embeds import (
    DEFAULT_REWRITE_HOSTS,
    PlatformToggles,
    RichLinkEmbedsConfigBody,
    _force_allowlisted_hosts,
)


def test_force_allowlisted_hosts_ignores_client_override() -> None:
    forced = _force_allowlisted_hosts({"twitter": "evil.example"})
    assert forced == DEFAULT_REWRITE_HOSTS
    assert forced["twitter"] == "fxtwitter.com"
    assert forced["bluesky"] == "bskx.app"
    assert "ddinstagram" not in str(forced)
    assert forced["instagram"] == "instagram7.com"
    assert forced["pixiv"] == "phixiv.net"
    assert forced["youtube_shorts"] == "youtu.be"


def test_new_platforms_default_false() -> None:
    platforms = PlatformToggles()
    assert platforms.instagram is False
    assert platforms.pixiv is False
    assert platforms.youtube_shorts is False
    assert platforms.twitter is True


def test_body_forces_hosts_on_dump_path() -> None:
    body = RichLinkEmbedsConfigBody(
        rewrite_hosts={  # type: ignore[arg-type]
            "twitter": "evil.example",
            "bluesky": "evil.example",
            "tiktok": "evil.example",
            "instagram": "evil.example",
            "reddit": "evil.example",
            "pixiv": "evil.example",
            "youtube_shorts": "evil.example",
        }
    )
    # Client can parse arbitrary strings into the model, but the route helper
    # is what persists — verify the force helper is authoritative.
    assert _force_allowlisted_hosts(body.rewrite_hosts.model_dump()) == DEFAULT_REWRITE_HOSTS


def test_partial_stored_platforms_fill_new_keys_false() -> None:
    config = RichLinkEmbedsConfigBody.model_validate(
        {
            "platforms": {
                "twitter": True,
                "bluesky": False,
                "tiktok": True,
                "reddit": True,
            }
        }
    )
    assert config.platforms.instagram is False
    assert config.platforms.pixiv is False
    assert config.platforms.youtube_shorts is False
    assert config.platforms.bluesky is False
