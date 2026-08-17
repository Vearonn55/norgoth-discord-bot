"""Level-up threshold scale: curve stretching + live level derivation.

The scale stretches (>1) or compresses (<1) the XP curve without ever rewriting
stored XP; levels are always re-derived from stored XP, so a config change takes
effect immediately.
"""

from __future__ import annotations

from app.routes.leveling import (
    DEFAULT_LEVEL_THRESHOLD_SCALE,
    LEVEL_THRESHOLD_SCALE_MAX,
    LEVEL_THRESHOLD_SCALE_MIN,
    clamp_threshold_scale,
    legacy_text_xp_from_total,
    level_from_xp,
    progression_xp,
    xp_for_level,
)


def test_clamp_threshold_scale_bounds_and_fallback() -> None:
    assert clamp_threshold_scale(0.1) == LEVEL_THRESHOLD_SCALE_MIN
    assert clamp_threshold_scale(9.0) == LEVEL_THRESHOLD_SCALE_MAX
    assert clamp_threshold_scale(1.25) == 1.25
    # Non-numeric input fails safe to the default.
    assert clamp_threshold_scale("nope") == DEFAULT_LEVEL_THRESHOLD_SCALE  # type: ignore[arg-type]


def test_default_scale_matches_classic_curve() -> None:
    # Level 1 requires 100 XP in the classic MEE6 curve.
    assert xp_for_level(1) == 100
    # Level 2 adds 5*1 + 50 + 100 = 155 => 255 total.
    assert xp_for_level(2) == 255


def test_scale_stretches_and_compresses_requirements() -> None:
    base = xp_for_level(5)
    assert xp_for_level(5, 2.0) == base * 2
    assert xp_for_level(5, 0.5) == round(base * 0.5)


def test_higher_scale_yields_lower_or_equal_level_for_same_xp() -> None:
    xp = 1000
    easy_level = level_from_xp(xp, 0.5)
    default_level = level_from_xp(xp, 1.0)
    hard_level = level_from_xp(xp, 2.0)

    # Stretching the curve (higher scale) makes a fixed XP total worth fewer
    # levels; compressing it makes the same XP worth more.
    assert easy_level >= default_level >= hard_level


def test_progression_xp_uses_text_plus_voice_total() -> None:
    # Text 5k + voice 20k → level from 25k, not from the metric score.
    total = progression_xp(
        metric_xp=5_000,
        total_score=25_000,
        text_score=5_000,
        voice_score=20_000,
    )
    assert total == 25_000
    metric_only_level = level_from_xp(5_000)
    combined_level = level_from_xp(total)
    assert combined_level > metric_only_level


def test_legacy_text_heal_skips_when_voice_present() -> None:
    assert legacy_text_xp_from_total(25_000, None) == 25_000
    assert legacy_text_xp_from_total(25_000, 0) == 25_000
    assert legacy_text_xp_from_total(25_000, 20_000) == 5_000
    assert legacy_text_xp_from_total(20_000, 20_000) is None
