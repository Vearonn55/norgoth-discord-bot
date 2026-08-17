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
    persistable_webhook_avatar,
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
    assert (
        normalize_https_avatar_url("https://user:pass@files.kick.com/a.png")
        is None
    )
    assert normalize_https_avatar_url("https://127.0.0.1/a.png") is None
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


def test_persistable_source_avatar_allowlist() -> None:
    assert persistable_source_avatar("kick", "https://evil.example/a.png") is None
    assert persistable_source_avatar("youtube", "https://cdn.example.com/a.png") is None
    assert persistable_source_avatar("twitch", "javascript:alert(1)") is None
    assert persistable_source_avatar("kick", "http://files.kick.com/a.png") is None
    assert (
        persistable_source_avatar(
            "youtube", "https://yt3.ggpht.com/a.png"
        )
        == "https://yt3.ggpht.com/a.png"
    )
    assert (
        persistable_source_avatar(
            "twitch",
            "https://static-cdn.jtvnw.net/jtv_user_pictures/demo.png",
        )
        == "https://static-cdn.jtvnw.net/jtv_user_pictures/demo.png"
    )
    rewritten = persistable_source_avatar(
        "x", "https://pbs.twimg.com/profile_images/1/photo_normal.jpg"
    )
    assert rewritten == "https://pbs.twimg.com/profile_images/1/photo_200x200.jpg"


def test_persistable_webhook_avatar_allows_public_https() -> None:
    assert persistable_webhook_avatar(None) is None
    assert persistable_webhook_avatar("") is None
    assert persistable_webhook_avatar("javascript:alert(1)") is None
    assert persistable_webhook_avatar("http://cdn.discordapp.com/a.png") is None
    assert persistable_webhook_avatar("https://user:pass@cdn.example.com/a.png") is None
    assert persistable_webhook_avatar("https://127.0.0.1/a.png") is None
    assert persistable_webhook_avatar("https://cdn.example.com/a.png") == (
        "https://cdn.example.com/a.png"
    )
    assert persistable_webhook_avatar(
        "https://cdn.discordapp.com/avatars/1/a.png"
    ) == "https://cdn.discordapp.com/avatars/1/a.png"


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


@pytest.mark.asyncio
async def test_backfill_null_avatars_uses_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.content_notification_worker import backfill_null_avatars

    source = MagicMock()
    source.avatar_url = None
    source.platform = "kick"
    session = AsyncMock()
    session.scalars = AsyncMock(return_value=_ScalarResult([source]))
    session.commit = AsyncMock()

    class _Factory:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return False

    refresh = AsyncMock()
    monkeypatch.setattr(
        "app.services.content_notifications.avatar.refresh_stale_avatars",
        refresh,
    )
    await backfill_null_avatars(lambda: _Factory())
    refresh.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_source_keeps_stored_avatar_when_incoming_empty() -> None:
    from app.services.content_notifications.fanout import ensure_source

    session = AsyncMock()
    existing = MagicMock()
    existing.username = "demo"
    existing.display_name = "Demo"
    existing.profile_url = "https://kick.com/demo"
    existing.avatar_url = "https://files.kick.com/images/user/old.png"
    existing.metadata_json = {}
    existing.avatar_checked_at = None
    session.scalar = AsyncMock(return_value=existing)
    session.flush = AsyncMock()
    result = await ensure_source(
        session,
        platform="kick",
        platform_creator_id="42",
        username="demo",
        display_name="Demo",
        profile_url="https://kick.com/demo",
        avatar_url=None,
    )
    assert result.avatar_url == "https://files.kick.com/images/user/old.png"
    assert result.avatar_checked_at is not None


@pytest.mark.asyncio
async def test_resolve_account_returns_normalized_avatar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.content_platforms.types import (
        PlatformType,
        ResolvedCreator,
    )
    from app.routes.content_notifications import (
        ResolveAccountRequest,
        resolve_account,
    )

    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.availability_reason.return_value = None
    adapter.resolve_account = AsyncMock(
        return_value=ResolvedCreator(
            platform=PlatformType.KICK,
            platform_creator_id="42",
            username="demo",
            display_name="Demo",
            profile_url="https://kick.com/demo",
            avatar_url="https://files.kick.com/images/user/a.png",
            canonical_url="https://kick.com/demo",
        )
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.get_adapter",
        lambda _platform: adapter,
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.throttle",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.read_resolve_cache",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.write_resolve_cache",
        AsyncMock(),
    )
    payload = await resolve_account(
        guild_id="guild-a",
        body=ResolveAccountRequest(platform="kick", url="https://kick.com/demo"),
    )
    assert payload["avatar_url"] == "https://files.kick.com/images/user/a.png"
    assert payload["platform_creator_id"] == "42"


@pytest.mark.asyncio
async def test_resolve_account_maps_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.content_platforms.types import PlatformAdapterError
    from app.routes.content_notifications import (
        ResolveAccountRequest,
        resolve_account,
    )

    adapter = MagicMock()
    adapter.is_available.return_value = True
    adapter.resolve_account = AsyncMock(
        side_effect=PlatformAdapterError("missing", code="not_found")
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.get_adapter",
        lambda _platform: adapter,
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.throttle",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.read_resolve_cache",
        AsyncMock(return_value=None),
    )
    with pytest.raises(HTTPException) as exc:
        await resolve_account(
            guild_id="guild-a",
            body=ResolveAccountRequest(
                platform="kick", url="https://kick.com/missing"
            ),
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "not_found"


@pytest.mark.asyncio
async def test_resolve_account_maps_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.content_platforms.types import PlatformAdapterError
    from app.routes.content_notifications import (
        ResolveAccountRequest,
        resolve_account,
    )

    adapter = MagicMock()
    adapter.resolve_account = AsyncMock(
        side_effect=PlatformAdapterError("slow down", code="rate_limited")
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.get_adapter",
        lambda _platform: adapter,
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.throttle",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.routes.content_notifications.read_resolve_cache",
        AsyncMock(return_value=None),
    )
    with pytest.raises(HTTPException) as exc:
        await resolve_account(
            guild_id="guild-a",
            body=ResolveAccountRequest(platform="x", url="https://x.com/demo"),
        )
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "rate_limited"


@pytest.mark.asyncio
async def test_update_sender_style_guild_isolated() -> None:
    from uuid import uuid4

    from app.routes.content_notifications import (
        SenderStyleUpdateBody,
        update_sender_style,
    )

    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await update_sender_style(
            guild_id="guild-a",
            style_id=uuid4(),
            body=SenderStyleUpdateBody(display_name="Nope"),
            session=session,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_sender_style_omitted_avatar_keeps_existing() -> None:
    from uuid import uuid4

    from app.routes.content_notifications import (
        SenderStyleUpdateBody,
        update_sender_style,
    )

    session = AsyncMock()
    row = MagicMock()
    row.id = uuid4()
    row.display_name = "Old"
    row.avatar_url = "https://cdn.example.com/old.png"
    session.scalar = AsyncMock(return_value=row)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    payload = await update_sender_style(
        guild_id="guild-a",
        style_id=row.id,
        body=SenderStyleUpdateBody(display_name="New"),
        session=session,
    )
    assert row.display_name == "New"
    assert row.avatar_url == "https://cdn.example.com/old.png"
    assert payload["display_name"] == "New"


@pytest.mark.asyncio
async def test_update_sender_style_null_avatar_clears() -> None:
    from uuid import uuid4

    from app.routes.content_notifications import (
        SenderStyleUpdateBody,
        update_sender_style,
    )

    session = AsyncMock()
    row = MagicMock()
    row.id = uuid4()
    row.display_name = "Demo"
    row.avatar_url = "https://cdn.example.com/old.png"
    session.scalar = AsyncMock(return_value=row)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    body = SenderStyleUpdateBody.model_validate({"avatar_url": None})
    await update_sender_style(
        guild_id="guild-a",
        style_id=row.id,
        body=body,
        session=session,
    )
    assert row.avatar_url is None
    assert row.display_name == "Demo"


@pytest.mark.asyncio
async def test_update_sender_style_rejects_unsafe_avatar() -> None:
    from uuid import uuid4

    from app.routes.content_notifications import (
        SenderStyleUpdateBody,
        update_sender_style,
    )

    session = AsyncMock()
    row = MagicMock()
    row.id = uuid4()
    row.display_name = "Demo"
    row.avatar_url = "https://cdn.example.com/old.png"
    session.scalar = AsyncMock(return_value=row)
    with pytest.raises(HTTPException) as exc:
        await update_sender_style(
            guild_id="guild-a",
            style_id=row.id,
            body=SenderStyleUpdateBody(avatar_url="javascript:alert(1)"),
            session=session,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_avatar_url"
    assert row.avatar_url == "https://cdn.example.com/old.png"
    session.commit.assert_not_called()


def test_sender_webhook_identity_omits_invalid_avatar() -> None:
    from app.services.content_notifications.delivery import sender_webhook_identity

    missing = sender_webhook_identity(None)
    assert missing == (None, None)

    style = MagicMock()
    style.id = uuid4()
    style.display_name = "Custom"
    style.avatar_url = "https://cdn.discordapp.com/avatars/1/a.png"
    username, avatar = sender_webhook_identity(style)
    assert username == "Custom"
    assert avatar == "https://cdn.discordapp.com/avatars/1/a.png"

    style.avatar_url = "http://evil.example/a.png"
    username, avatar = sender_webhook_identity(style)
    assert username == "Custom"
    assert avatar is None
