"""Pagination, analytics, avatar, and template isolation tests for CN landing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routes.content_notifications import (
    TemplateBody,
    analytics,
    delivery_history,
    list_accounts,
    update_template,
)
from app.services.content_notifications.avatar import (
    normalize_https_avatar_url,
    parse_account_platform_filter,
    persistable_source_avatar,
    refresh_stale_avatars,
)


def test_parse_account_platform_filter() -> None:
    assert parse_account_platform_filter(None) is None
    assert parse_account_platform_filter("") is None
    assert parse_account_platform_filter("all") is None
    assert parse_account_platform_filter("YouTube") == "youtube"
    with pytest.raises(ValueError):
        parse_account_platform_filter("tiktok")
    with pytest.raises(ValueError):
        parse_account_platform_filter("unknown")


def test_normalize_https_avatar_url() -> None:
    assert normalize_https_avatar_url("javascript:alert(1)") is None
    assert normalize_https_avatar_url("data:image/png;base64,abc") is None
    assert normalize_https_avatar_url("http://example.com/a.png") is None
    assert (
        normalize_https_avatar_url("https://cdn.example.com/a.png")
        == "https://cdn.example.com/a.png"
    )
    rewritten = normalize_https_avatar_url(
        "https://pbs.twimg.com/profile_images/1/photo_normal.jpg"
    )
    assert rewritten is not None
    assert rewritten.endswith("_200x200.jpg")


def test_kick_thumbnails_are_not_persisted() -> None:
    assert (
        persistable_source_avatar(
            "kick", "https://images.kick.com/video/thumbnail.jpg"
        )
        is None
    )
    assert (
        persistable_source_avatar(
            "kick", "https://files.kick.com/images/user/a.png"
        )
        == "https://files.kick.com/images/user/a.png"
    )


@pytest.mark.asyncio
async def test_list_accounts_rejects_tiktok_filter() -> None:
    with pytest.raises(HTTPException) as exc:
        await list_accounts(
            guild_id="guild-a",
            session=AsyncMock(),
            platform="tiktok",
            limit=10,
            offset=0,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_platform"


class _ScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


@pytest.mark.asyncio
async def test_list_accounts_scopes_to_path_guild(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    captured: list[object] = []

    async def scalar(stmt: object) -> int:
        captured.append(stmt)
        return 2

    async def scalars(stmt: object) -> _ScalarResult:
        captured.append(stmt)
        return _ScalarResult([])

    session.scalar = scalar
    session.scalars = scalars
    session.commit = AsyncMock()
    monkeypatch.setattr(
        "app.routes.content_notifications.refresh_stale_avatars",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.guild_platform_usage",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.platform_availability",
        lambda: [],
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.worker_online",
        AsyncMock(return_value=True),
    )

    payload = await list_accounts(
        guild_id="guild-a",
        session=session,
        platform="youtube",
        limit=10,
        offset=10,
    )
    assert payload["total"] == 2
    assert payload["limit"] == 10
    assert payload["offset"] == 10
    compiled = " ".join(
        str(stmt.compile(compile_kwargs={"literal_binds": True})) for stmt in captured
    )
    assert "guild-a" in compiled
    assert "youtube" in compiled
    assert "guild-b" not in compiled


@pytest.mark.asyncio
async def test_history_includes_total() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=4)
    session.execute = AsyncMock(return_value=_ScalarResult([]))
    payload = await delivery_history(
        guild_id="guild-a",
        session=session,
        platform=None,
        status=None,
        limit=50,
        offset=0,
    )
    assert payload["total"] == 4
    assert payload["items"] == []
    count_stmt = session.scalar.await_args.args[0]
    compiled = str(count_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "guild-a" in compiled


@pytest.mark.asyncio
async def test_analytics_series_are_guild_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=0)
    session.execute = AsyncMock(return_value=_ScalarResult([]))
    monkeypatch.setattr(
        "app.routes.content_notifications.worker_online",
        AsyncMock(return_value=True),
    )
    payload = await analytics(guild_id="guild-a", session=session, days=30)
    assert payload["series"] == []
    assert "range_start" in payload
    assert "event_type_distribution" in payload
    compiled = " ".join(
        str(call.args[0].compile(compile_kwargs={"literal_binds": True}))
        for call in session.execute.await_args_list
    )
    assert "guild-a" in compiled
    assert "guild-b" not in compiled


@pytest.mark.asyncio
async def test_update_template_rejects_foreign_guild() -> None:
    session = AsyncMock()
    row = MagicMock()
    row.guild_id = "other-guild"
    session.scalar = AsyncMock(return_value=row)
    with pytest.raises(HTTPException) as exc:
        await update_template(
            guild_id="guild-a",
            template_id=uuid4(),
            body=TemplateBody(name="Hello", content="Hi"),
            session=session,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_avatar_refresh_skips_when_redis_lock_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis_client = AsyncMock()
    redis_client.set = AsyncMock(return_value=None)
    redis_client.aclose = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.queue.get_redis",
        AsyncMock(return_value=redis_client),
    )
    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.resolve_account = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.avatar.get_adapter",
        lambda _platform: adapter,
    )
    source = MagicMock()
    source.id = uuid4()
    source.platform = "youtube"
    source.avatar_url = None
    source.avatar_checked_at = None
    source.canonical_url = "https://youtube.com/@norgoth"
    source.profile_url = "https://youtube.com/@norgoth"
    await refresh_stale_avatars(AsyncMock(), [source])
    adapter.resolve_account.assert_not_called()
