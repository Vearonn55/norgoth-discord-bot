"""Content Notifications provider webhook, adapter, and OAuth scaffold tests."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.content_platforms.tiktok.adapter import TikTokAdapter
from app.integrations.content_platforms.twitch.adapter import (
    TwitchAdapter,
    verify_twitch_signature,
)
from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
    PlatformBlockedError,
    PlatformRawEvent,
    PlatformType,
    ResolvedCreator,
)
from app.integrations.content_platforms.youtube.adapter import (
    YouTubeAdapter,
    parse_websub_atom,
)
from app.security.pkce import generate_pkce, verify_pkce
from app.security.provider_oauth_state import (
    InvalidProviderOAuthStateError,
    ProviderOAuthStateService,
)


def test_verify_twitch_signature_valid() -> None:
    secret = "supersecret"
    message_id = "msg-1"
    timestamp = "2026-08-13T00:00:00Z"
    body = b'{"challenge":"abc"}'
    digest = hmac.new(
        secret.encode(),
        message_id.encode() + timestamp.encode() + body,
        hashlib.sha256,
    ).hexdigest()
    assert verify_twitch_signature(
        secret=secret,
        message_id=message_id,
        timestamp=timestamp,
        body=body,
        signature=f"sha256={digest}",
    )


def test_verify_twitch_signature_rejects_tamper() -> None:
    secret = "supersecret"
    message_id = "msg-1"
    timestamp = "2026-08-13T00:00:00Z"
    body = b'{"ok":true}'
    digest = hmac.new(
        secret.encode(),
        message_id.encode() + timestamp.encode() + body,
        hashlib.sha256,
    ).hexdigest()
    assert not verify_twitch_signature(
        secret=secret,
        message_id=message_id,
        timestamp=timestamp,
        body=b'{"ok":false}',
        signature=f"sha256={digest}",
    )


@pytest.mark.anyio
async def test_twitch_enrich_offline_event() -> None:
    adapter = TwitchAdapter(http_client=AsyncMock())
    raw = PlatformRawEvent(
        platform=PlatformType.TWITCH,
        event_type=ContentEventType.STREAM_ENDED,
        external_content_id="offline-1",
        platform_creator_id="123",
        raw={
            "subscription": {"type": "stream.offline"},
            "event": {
                "broadcaster_user_id": "123",
                "broadcaster_user_login": "demo",
                "broadcaster_user_name": "Demo",
                "id": "offline-1",
            },
        },
    )
    event = await adapter.enrich_event(raw)
    assert event.event_type == ContentEventType.STREAM_ENDED
    assert event.is_live is False


def test_youtube_websub_atom_parse_and_duplicate_ids() -> None:
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <entry>
        <yt:videoId>vid1</yt:videoId>
        <yt:channelId>UCabcdefghijklmnopqrstuv</yt:channelId>
        <title>One</title>
        <published>2026-08-13T00:00:00+00:00</published>
        <link href="https://www.youtube.com/watch?v=vid1"/>
      </entry>
      <entry>
        <yt:videoId>vid1</yt:videoId>
        <yt:channelId>UCabcdefghijklmnopqrstuv</yt:channelId>
        <title>One again</title>
        <published>2026-08-13T00:01:00+00:00</published>
        <link href="https://www.youtube.com/watch?v=vid1"/>
      </entry>
    </feed>
    """
    events = parse_websub_atom(xml)
    assert len(events) == 2
    assert events[0].external_content_id == "vid1"
    assert events[0].platform_creator_id == "UCabcdefghijklmnopqrstuv"


@pytest.mark.anyio
async def test_youtube_resolve_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    adapter = YouTubeAdapter()
    assert adapter.is_available() is False
    with pytest.raises(Exception) as exc:
        await adapter.resolve_account("@SomeHandle")
    assert "YOUTUBE_API_KEY" in str(exc.value)


@pytest.mark.anyio
async def test_youtube_resolve_handle_uses_data_api_not_scrape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"items": [{"id": "UCabcdefghijklmnopqrstuv"}]}
    client.get = AsyncMock(return_value=response)
    profile = MagicMock()
    profile.status_code = 200
    profile.json.return_value = {
        "items": [
            {
                "snippet": {
                    "title": "Demo",
                    "customUrl": "@demo",
                    "thumbnails": {"default": {"url": "https://yt3.ggpht.com/a.png"}},
                }
            }
        ]
    }

    async def get_side_effect(url, params=None, **_kwargs):
        if "forHandle" in (params or {}):
            return response
        return profile

    client.get = AsyncMock(side_effect=get_side_effect)
    adapter = YouTubeAdapter(http_client=client)
    creator = await adapter.resolve_account("@demo")
    assert creator.platform_creator_id == "UCabcdefghijklmnopqrstuv"
    assert creator.avatar_url == "https://yt3.ggpht.com/a.png"
    assert creator.display_name == "Demo"
    # Never hit youtube.com HTML pages.
    for call in client.get.await_args_list:
        assert "googleapis.com" in call.args[0]


@pytest.mark.anyio
async def test_youtube_resolve_prefers_medium_when_high_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "items": [
            {
                "id": "UCabcdefghijklmnopqrstuv",
                "snippet": {
                    "title": "Demo",
                    "customUrl": "@demo",
                    "thumbnails": {
                        "medium": {"url": "https://yt3.ggpht.com/medium.png"},
                        "default": {"url": "https://yt3.ggpht.com/default.png"},
                    },
                },
            }
        ]
    }
    client.get = AsyncMock(return_value=response)
    adapter = YouTubeAdapter(http_client=client)
    creator = await adapter.resolve_account("UCabcdefghijklmnopqrstuv")
    assert creator.avatar_url == "https://yt3.ggpht.com/medium.png"


@pytest.mark.anyio
async def test_youtube_resolve_survives_snippet_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    client = AsyncMock()
    handle_response = MagicMock()
    handle_response.status_code = 200
    handle_response.json.return_value = {"items": [{"id": "UCabcdefghijklmnopqrstuv"}]}
    snippet_response = MagicMock()
    snippet_response.status_code = 500
    snippet_response.json.return_value = {}

    async def get_side_effect(url, params=None, **_kwargs):
        if "forHandle" in (params or {}):
            return handle_response
        return snippet_response

    client.get = AsyncMock(side_effect=get_side_effect)
    adapter = YouTubeAdapter(http_client=client)
    with caplog.at_level("WARNING"):
        creator = await adapter.resolve_account("@demo")
    assert creator.platform_creator_id == "UCabcdefghijklmnopqrstuv"
    assert creator.avatar_url is None
    assert "snippet failed" in caplog.text


@pytest.mark.anyio
async def test_twitch_resolve_maps_profile_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWITCH_CLIENT_ID", "id")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "secret")
    client = AsyncMock()
    adapter = TwitchAdapter(http_client=client)
    adapter._token = "tok"
    user_response = MagicMock()
    user_response.status_code = 200
    user_response.json.return_value = {
        "data": [
            {
                "id": "123",
                "login": "demo",
                "display_name": "Demo",
                "profile_image_url": (
                    "https://static-cdn.jtvnw.net/jtv_user_pictures/demo.png"
                ),
            }
        ]
    }
    client.get = AsyncMock(return_value=user_response)
    creator = await adapter.resolve_account("https://www.twitch.tv/demo")
    assert creator.platform_creator_id == "123"
    assert creator.avatar_url == (
        "https://static-cdn.jtvnw.net/jtv_user_pictures/demo.png"
    )
    assert creator.display_name == "Demo"


@pytest.mark.anyio
async def test_x_resolve_maps_profile_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("X_API_BEARER_TOKEN", "bearer")
    monkeypatch.delenv("X_MONTHLY_READ_BUDGET", raising=False)
    monkeypatch.setattr(
        "app.services.content_notifications.x_budget.budget_exhausted",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.content_notifications.x_budget.record_reads",
        AsyncMock(return_value=1),
    )
    client = AsyncMock()
    user_response = MagicMock()
    user_response.status_code = 200
    user_response.json.return_value = {
        "data": {
            "id": "99",
            "username": "demo",
            "name": "Demo",
            "profile_image_url": (
                "https://pbs.twimg.com/profile_images/1/photo_normal.jpg"
            ),
        }
    }
    client.get = AsyncMock(return_value=user_response)
    from app.integrations.content_platforms.x.adapter import XAdapter

    adapter = XAdapter(http_client=client)
    creator = await adapter.resolve_account("https://x.com/demo")
    assert creator.platform_creator_id == "99"
    assert creator.avatar_url == (
        "https://pbs.twimg.com/profile_images/1/photo_normal.jpg"
    )


@pytest.mark.anyio
async def test_kick_resolve_uses_users_profile_picture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICK_CLIENT_ID", "id")
    monkeypatch.setenv("KICK_CLIENT_SECRET", "secret")
    from app.integrations.content_platforms.kick.adapter import KickAdapter

    adapter = KickAdapter(http_client=AsyncMock())
    adapter._token = "tok"
    adapter._token_expires_at = 9_999_999_999

    async def request(method, url, params=None, json=None, headers=None):
        resp = MagicMock()
        resp.status_code = 200
        if "/channels" in url:
            resp.json.return_value = {
                "data": [
                    {
                        "broadcaster_user_id": 42,
                        "slug": "demo",
                        "channel_name": "Demo",
                    }
                ]
            }
        else:
            resp.json.return_value = {
                "data": [
                    {
                        "user_id": 42,
                        "name": "Demo",
                        "profile_picture": (
                            "https://files.kick.com/images/user/a.png"
                        ),
                    }
                ]
            }
        return resp

    adapter._http.request = AsyncMock(side_effect=request)
    creator = await adapter.resolve_account("https://kick.com/demo")
    assert creator.platform_creator_id == "42"
    assert creator.username == "demo"
    assert creator.display_name == "Demo"
    assert creator.avatar_url == "https://files.kick.com/images/user/a.png"
    urls = [call.args[1] for call in adapter._http.request.await_args_list]
    assert any("/users" in url for url in urls)


@pytest.mark.anyio
async def test_kick_resolve_survives_users_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICK_CLIENT_ID", "id")
    monkeypatch.setenv("KICK_CLIENT_SECRET", "secret")
    from app.integrations.content_platforms.kick.adapter import KickAdapter

    adapter = KickAdapter(http_client=AsyncMock())
    adapter._token = "tok"
    adapter._token_expires_at = 9_999_999_999

    async def request(method, url, params=None, json=None, headers=None):
        resp = MagicMock()
        if "/channels" in url:
            resp.status_code = 200
            resp.json.return_value = {
                "data": [{"broadcaster_user_id": 42, "slug": "demo"}]
            }
        else:
            resp.status_code = 404
            resp.json.return_value = {}
        return resp

    adapter._http.request = AsyncMock(side_effect=request)
    creator = await adapter.resolve_account("https://kick.com/demo")
    assert creator.platform_creator_id == "42"
    assert creator.username == "demo"
    assert creator.avatar_url is None


@pytest.mark.anyio
async def test_tiktok_remains_blocked() -> None:
    adapter = TikTokAdapter()
    assert adapter.is_available() is False
    assert adapter.supports_push() is False
    with pytest.raises(PlatformBlockedError):
        await adapter.resolve_account("https://www.tiktok.com/@someone")


def test_pkce_roundtrip() -> None:
    pair = generate_pkce()
    assert pair.method == "S256"
    assert verify_pkce(verifier=pair.verifier, challenge=pair.challenge)
    assert not verify_pkce(verifier="wrong", challenge=pair.challenge)


def test_provider_oauth_state_binding_and_expiry() -> None:
    service = ProviderOAuthStateService(secret="unit-test-secret", lifetime_seconds=60)
    now = int(datetime(2026, 8, 13, tzinfo=timezone.utc).timestamp())
    state, parsed = service.create(
        user_id="user-1",
        guild_id="guild-1",
        provider="tiktok",
        purpose="tiktok_display",
        with_pkce=True,
        current_time=now,
    )
    assert parsed.pkce_verifier
    ok = service.verify(
        state,
        expected_provider="tiktok",
        expected_user_id="user-1",
        expected_guild_id="guild-1",
        current_time=now + 10,
    )
    assert ok.provider == "tiktok"
    with pytest.raises(InvalidProviderOAuthStateError):
        service.verify(state, expected_provider="twitch", current_time=now + 10)
    with pytest.raises(InvalidProviderOAuthStateError):
        service.verify(state, expected_guild_id="other", current_time=now + 10)
    with pytest.raises(InvalidProviderOAuthStateError):
        service.verify(state, current_time=now + 120)


@pytest.mark.anyio
async def test_x_budget_exhaustion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_MONTHLY_READ_BUDGET", "2")
    store: dict[str, int] = {}

    class FakeRedis:
        async def get(self, key: str):
            value = store.get(key)
            return None if value is None else str(value)

        async def incrby(self, key: str, amount: int):
            store[key] = store.get(key, 0) + amount
            return store[key]

        async def expire(self, key: str, ttl: int):
            return True

        async def aclose(self):
            return None

    fake = FakeRedis()
    with patch(
        "app.services.content_notifications.x_budget.get_redis",
        AsyncMock(return_value=fake),
    ):
        from app.services.content_notifications import x_budget

        assert await x_budget.budget_exhausted() is False
        await x_budget.record_reads(2)
        assert await x_budget.budget_exhausted() is True


@pytest.mark.anyio
async def test_mark_replay_dedupe() -> None:
    store: dict[str, str] = {}

    class FakeRedis:
        async def set(self, key, value, nx=False, ex=None):
            if nx and key in store:
                return False
            store[key] = value
            return True

        async def aclose(self):
            return None

    with patch(
        "app.services.content_notifications.queue.get_redis",
        AsyncMock(return_value=FakeRedis()),
    ):
        from app.services.content_notifications.queue import mark_replay

        assert await mark_replay("twitch:abc") is True
        assert await mark_replay("twitch:abc") is False


@pytest.mark.anyio
async def test_kick_fetch_latest_from_channel_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICK_CLIENT_ID", "id")
    monkeypatch.setenv("KICK_CLIENT_SECRET", "secret")
    from app.integrations.content_platforms.kick.adapter import KickAdapter

    adapter = KickAdapter(http_client=AsyncMock())
    adapter._token = "tok"
    adapter._token_expires_at = 9_999_999_999

    channel_response = MagicMock()
    channel_response.status_code = 200
    channel_response.json.return_value = {
        "data": [
            {
                "broadcaster_user_id": 42,
                "slug": "demo",
                "stream_title": "Friday Night",
                "category": {"id": 1, "name": "Just Chatting"},
                "stream": {
                    "is_live": True,
                    "start_time": "2026-08-13T10:00:00Z",
                    "thumbnail": "https://example.com/thumb.jpg",
                    "url": "https://kick.com/demo",
                    "viewer_count": 12,
                },
            }
        ]
    }
    adapter._http.request = AsyncMock(return_value=channel_response)

    creator = ResolvedCreator(
        platform=PlatformType.KICK,
        platform_creator_id="42",
        username="demo",
        display_name="Demo",
        profile_url="https://kick.com/demo",
    )
    events = await adapter.fetch_latest(creator, limit=1)
    assert len(events) == 1
    assert events[0].event_type == ContentEventType.STREAM_STARTED
    assert events[0].title == "Friday Night"
    assert events[0].external_content_id == "42:2026-08-13T10:00:00Z"
    assert events[0].is_live is True


@pytest.mark.anyio
async def test_kick_fetch_latest_offline_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KICK_CLIENT_ID", "id")
    monkeypatch.setenv("KICK_CLIENT_SECRET", "secret")
    from app.integrations.content_platforms.kick.adapter import KickAdapter

    adapter = KickAdapter(http_client=AsyncMock())
    adapter._token = "tok"
    adapter._token_expires_at = 9_999_999_999

    channel_response = MagicMock()
    channel_response.status_code = 200
    channel_response.json.return_value = {
        "data": [
            {
                "broadcaster_user_id": 42,
                "slug": "demo",
                "stream_title": "",
                "stream": {"is_live": False},
            }
        ]
    }
    users_response = MagicMock()
    users_response.status_code = 200
    users_response.json.return_value = {"data": []}
    legacy_response = MagicMock()
    legacy_response.status_code = 200
    legacy_response.json.return_value = {"data": []}

    adapter._http.request = AsyncMock(
        side_effect=[channel_response, users_response, legacy_response]
    )

    creator = ResolvedCreator(
        platform=PlatformType.KICK,
        platform_creator_id="42",
        username="demo",
        display_name="Demo",
        profile_url="https://kick.com/demo",
    )
    assert await adapter.fetch_latest(creator) == []


@pytest.mark.anyio
async def test_kick_enrich_offline_event() -> None:
    from app.integrations.content_platforms.kick.adapter import KickAdapter

    adapter = KickAdapter(http_client=AsyncMock())
    raw = PlatformRawEvent(
        platform=PlatformType.KICK,
        event_type=ContentEventType.STREAM_ENDED,
        external_content_id="42:ended",
        platform_creator_id="42",
        raw={
            "broadcaster": {
                "user_id": 42,
                "username": "demo",
                "channel_slug": "demo",
                "profile_picture": "https://example.com/a.png",
            },
            "is_live": False,
            "title": "Was live",
            "started_at": "2026-08-13T10:00:00Z",
            "ended_at": "2026-08-13T12:00:00Z",
        },
    )
    event = await adapter.enrich_event(raw)
    assert event.event_type == ContentEventType.STREAM_ENDED
    assert event.is_live is False
    assert event.content_url == "https://kick.com/demo"
    assert event.thumbnail_url is None


@pytest.mark.anyio
async def test_kick_enrich_live_event_uses_fetch_latest_thumbnail() -> None:
    from app.integrations.content_platforms.kick.adapter import KickAdapter

    adapter = KickAdapter(http_client=AsyncMock())
    live = NormalizedContentEvent(
        platform=PlatformType.KICK,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="42:live",
        creator_platform_id="42",
        creator_name="Demo",
        title="Friday Night",
        content_url="https://kick.com/demo",
        thumbnail_url="https://kick.com/thumbs/live.jpg",
        is_live=True,
        game="Just Chatting",
        viewer_count=12,
    )
    adapter.fetch_latest = AsyncMock(return_value=[live])
    raw = PlatformRawEvent(
        platform=PlatformType.KICK,
        event_type=ContentEventType.STREAM_STARTED,
        external_content_id="42:started",
        platform_creator_id="42",
        raw={
            "broadcaster": {
                "user_id": 42,
                "username": "demo",
                "channel_slug": "demo",
                "profile_picture": "https://example.com/a.png",
            },
            "is_live": True,
            "title": "Going live",
            "started_at": "2026-08-13T10:00:00Z",
        },
    )
    event = await adapter.enrich_event(raw)
    assert event.is_live is True
    assert event.thumbnail_url == "https://kick.com/thumbs/live.jpg"
    assert event.title == "Friday Night"
    assert event.game == "Just Chatting"
    adapter.fetch_latest.assert_awaited_once()


def test_manual_test_event_synthesizes_when_offline() -> None:
    from app.routes.content_notifications import _manual_test_event
    from uuid import uuid4

    creator = ResolvedCreator(
        platform=PlatformType.KICK,
        platform_creator_id="42",
        username="demo",
        display_name="Demo",
        profile_url="https://kick.com/demo",
    )
    event = _manual_test_event(
        creator=creator,
        subscription_id=uuid4(),
        latest=None,
        event_types=["STREAM_STARTED"],
    )
    assert event.event_type == ContentEventType.STREAM_STARTED
    assert event.external_content_id.startswith("manual-test:")
    assert event.raw_metadata.get("synthetic") is True
    assert event.title.startswith("[Test]")


def test_fanout_result_defers_enqueue() -> None:
    """Fanout must return job ids without touching Redis (commit-then-enqueue)."""

    import inspect
    from app.services.content_notifications import fanout as fanout_mod

    source = inspect.getsource(fanout_mod.persist_and_fanout)
    assert "enqueue_job" not in source
    assert "FanoutResult" in source
