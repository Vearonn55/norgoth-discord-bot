"""Link Embeds API config helpers — host allowlist + platform defaults."""

from __future__ import annotations

from app.routes.rich_link_embeds import (
    DEFAULT_REWRITE_HOSTS,
    PlatformToggles,
    RichLinkEmbedsConfigBody,
    _force_allowlisted_hosts,
)
from app.services.rich_link_embeds_normalize import (
    disable_tiktok_for_downgrade,
    normalize_rich_link_embeds_config,
    stored_needs_link_embeds_normalize,
)


def test_force_allowlisted_hosts_ignores_client_override() -> None:
    forced = _force_allowlisted_hosts({"twitter": "evil.example"})
    assert forced == DEFAULT_REWRITE_HOSTS
    assert forced["twitter"] == "fxtwitter.com"
    assert forced["tiktok"] == "tnktok.com"
    assert "bluesky" not in forced
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
    assert not hasattr(platforms, "bluesky")


def test_body_forces_hosts_on_dump_path() -> None:
    body = RichLinkEmbedsConfigBody(
        rewrite_hosts={  # type: ignore[arg-type]
            "twitter": "evil.example",
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
                "tiktok": True,
                "reddit": True,
            }
        }
    )
    assert config.platforms.instagram is False
    assert config.platforms.pixiv is False
    assert config.platforms.youtube_shorts is False
    dumped = config.platforms.model_dump()
    assert "bluesky" not in dumped


def test_normalize_remaps_vxtiktok_and_drops_bluesky() -> None:
    payload = {
        "enabled": True,
        "platforms": {
            "twitter": True,
            "bluesky": True,
            "tiktok": True,
            "reddit": False,
        },
        "rewrite_hosts": {
            "twitter": "fxtwitter.com",
            "bluesky": "bskx.app",
            "tiktok": "vxtiktok.com",
        },
    }
    assert stored_needs_link_embeds_normalize(payload) is True
    out = normalize_rich_link_embeds_config(payload)
    assert "bluesky" not in out["platforms"]
    assert out["platforms"]["tiktok"] is True
    assert out["platforms"]["reddit"] is False
    assert out["rewrite_hosts"]["tiktok"] == "tnktok.com"
    assert "bluesky" not in out["rewrite_hosts"]
    assert "vxtiktok" not in str(out["rewrite_hosts"])
    assert stored_needs_link_embeds_normalize(out) is False


def test_normalize_empty_does_not_flag() -> None:
    assert stored_needs_link_embeds_normalize({}) is False
    assert stored_needs_link_embeds_normalize(None) is False


def test_downgrade_disables_tiktok_without_vxtiktok() -> None:
    rolled = disable_tiktok_for_downgrade(
        {"platforms": {"tiktok": True}, "rewrite_hosts": {"tiktok": "tnktok.com"}}
    )
    assert rolled["platforms"]["tiktok"] is False
    assert rolled["rewrite_hosts"]["tiktok"] == "tnktok.com"
    assert "vxtiktok" not in str(rolled)
