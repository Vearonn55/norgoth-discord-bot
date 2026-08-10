"""Population-derived analytics KPIs (net growth, churn, retention).

These exercise the pure ``_population_metrics`` helper that turns per-day
member_count snapshots + leave events into normalized growth/retention numbers.
"""

from __future__ import annotations

from typing import Any

from app.routes.analytics import _population_metrics


def _point(day: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "date": day,
        "messages": 0,
        "unique_authors": 0,
        "joins": 0,
        "rejoins": 0,
        "leaves": 0,
        "voice_uniques": 0,
        "member_count": None,
        "has_data": True,
    }
    base.update(overrides)
    return base


def test_no_snapshots_yields_null_population_metrics() -> None:
    series = [_point("2026-01-01", joins=5, leaves=2)]
    metrics = _population_metrics(series)

    assert metrics["start_members"] is None
    assert metrics["end_members"] is None
    assert metrics["net_member_change"] is None
    assert metrics["net_growth_rate"] is None
    assert metrics["churn_rate"] is None
    assert metrics["retention_rate"] is None
    # New members still counts first-time joins even without snapshots.
    assert metrics["new_members"] == 5


def test_net_growth_uses_population_delta_not_join_leave() -> None:
    series = [
        _point("2026-01-01", member_count=100, joins=10, leaves=4),
        _point("2026-01-02", member_count=130, joins=2, leaves=1),
    ]
    metrics = _population_metrics(series)

    assert metrics["start_members"] == 100
    assert metrics["end_members"] == 130
    # Population grew by 30 even though joins - leaves would be 12 - 5 = 7.
    assert metrics["net_member_change"] == 30
    assert metrics["net_growth_rate"] == 0.30


def test_churn_and_retention_normalized_to_start_population() -> None:
    series = [
        _point("2026-01-01", member_count=200, leaves=5),
        _point("2026-01-02", member_count=205, leaves=15),
    ]
    metrics = _population_metrics(series)

    # 20 leaves over a starting population of 200 => 10% churn, 90% retention.
    assert metrics["churn_rate"] == 0.10
    assert metrics["retention_rate"] == 0.90


def test_retention_floored_at_zero_for_extreme_churn() -> None:
    series = [
        _point("2026-01-01", member_count=10, leaves=8),
        _point("2026-01-02", member_count=6, leaves=7),
    ]
    metrics = _population_metrics(series)

    # 15 leaves / 10 start => churn 1.5, retention floored to 0.
    assert metrics["churn_rate"] == 1.5
    assert metrics["retention_rate"] == 0.0
