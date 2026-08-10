"""Leaderboard metric selection (text vs voice XP)."""

from __future__ import annotations

from app.routes.leveling import xp_key, xp_text_key, xp_voice_key


def test_xp_redis_key_split() -> None:
    guild = "123456789012345678"
    assert xp_key(guild) == f"norgoth:guild:{guild}:xp"
    assert xp_text_key(guild) == f"norgoth:guild:{guild}:xp:text"
    assert xp_voice_key(guild) == f"norgoth:guild:{guild}:xp:voice"
    assert xp_text_key(guild) != xp_voice_key(guild)
    assert xp_key(guild) != xp_text_key(guild)


def test_net_upvotes_is_accepted_metric_literal() -> None:
    from typing import get_args

    from app.routes.leveling import XpMetric

    assert "net_upvotes" in get_args(XpMetric)
    assert "text" in get_args(XpMetric)
    assert "voice" in get_args(XpMetric)
