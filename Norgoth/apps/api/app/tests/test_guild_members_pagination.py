"""Unit tests for guild member snapshot pagination helpers."""

from __future__ import annotations

from app.services.guild_member_snapshot import (
    filter_members,
    merge_include_members,
    paginate_members,
    parse_include_member_ids,
    sort_members_deterministic,
)


def _member(
    member_id: str,
    *,
    name: str,
    display_name: str | None = None,
    bot: bool = False,
) -> dict:
    return {
        "id": member_id,
        "name": name,
        "display_name": display_name,
        "bot": bot,
    }


def test_sort_members_deterministic() -> None:
    members = [
        _member("3", name="charlie"),
        _member("1", name="alpha"),
        _member("2", name="bravo", display_name="Bravo"),
    ]
    sorted_members = sort_members_deterministic(members)
    assert [member["id"] for member in sorted_members] == ["1", "2", "3"]


def test_filter_members_search_and_exclude_bots() -> None:
    members = [
        _member("1", name="alpha"),
        _member("2", name="beta-bot", bot=True),
        _member("3", name="gamma"),
    ]
    filtered = filter_members(members, q="a", exclude_bots=True)
    assert [member["id"] for member in filtered] == ["1", "3"]


def test_paginate_members_metadata() -> None:
    members = [_member(str(index), name=f"m-{index}") for index in range(25)]
    page_members, pagination = paginate_members(members, offset=10, limit=10)
    assert len(page_members) == 10
    assert pagination["page"] == 2
    assert pagination["total"] == 25
    assert pagination["total_pages"] == 3
    assert pagination["has_previous"] is True
    assert pagination["has_next"] is True


def test_paginate_members_clamps_empty_page() -> None:
    members = [_member("1", name="alpha")]
    page_members, pagination = paginate_members(members, offset=100, limit=10)
    assert len(page_members) == 1
    assert pagination["page"] == 1


def test_merge_include_members_adds_off_page_rows() -> None:
    members = [
        _member("1", name="alpha"),
        _member("2", name="bravo"),
        _member("3", name="charlie"),
    ]
    page_members, _ = paginate_members(members, offset=0, limit=1)
    merged = merge_include_members(page_members, members, ["3"])
    assert [member["id"] for member in merged] == ["3", "1"]


def test_parse_include_member_ids_dedupes_and_caps() -> None:
    ids = ["111", "111", "222", "bad"] + [str(1000 + index) for index in range(120)]
    parsed = parse_include_member_ids(",".join(ids))
    assert parsed[:3] == ["111", "222", "1000"]
    assert len(parsed) == 100


def test_exempt_only_filter() -> None:
    members = [
        _member("1", name="alpha"),
        _member("2", name="bravo"),
        _member("3", name="charlie"),
    ]
    filtered = filter_members(
        members,
        only_member_ids={"2", "3"},
    )
    assert [member["id"] for member in filtered] == ["2", "3"]
