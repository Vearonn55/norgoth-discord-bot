"""Unit tests for voice-aware legacy XP heals."""

from bot.leveling import legacy_text_xp_from_total, level_from_xp


def test_legacy_text_heal_does_not_copy_total_when_voice_exists() -> None:
    assert legacy_text_xp_from_total(25_000, None) == 25_000.0
    assert legacy_text_xp_from_total(25_000, 20_000) == 5_000.0
    assert legacy_text_xp_from_total(20_000, 20_000) is None


def test_leaderboard_level_uses_combined_xp() -> None:
    metric_xp = 5_000
    total_xp = 25_000
    assert level_from_xp(total_xp) > level_from_xp(metric_xp)
