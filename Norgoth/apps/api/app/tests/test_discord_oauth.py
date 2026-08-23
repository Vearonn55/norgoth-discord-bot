"""Tests for the Discord OAuth2 client."""

from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.integrations.discord.oauth import (
    DASHBOARD_OAUTH_SCOPES,
    DiscordOAuthClient,
    DiscordOAuthError,
    VERIFICATION_OAUTH_SCOPES,
)

CLIENT_ID = "123456789012345678"
CLIENT_SECRET = "discord-client-secret"
REDIRECT_URI = "https://verify.example.com/api/v1/oauth/discord/callback"
ACCESS_TOKEN = "discord-access-token"


def _build_client(
    http_client: AsyncMock,
) -> DiscordOAuthClient:
    """Create a Discord OAuth client for tests."""

    return DiscordOAuthClient(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        http_client=http_client,
    )


def _build_response(
    payload: object,
    *,
    status_code: int = 200,
) -> MagicMock:
    """Create an HTTP response mock."""

    response = MagicMock(spec=httpx.Response)
    response.json.return_value = payload
    response.status_code = status_code
    response.is_success = 200 <= status_code < 300
    response.headers = {}
    response.raise_for_status.return_value = None

    return response


def test_build_authorization_url_contains_required_parameters() -> None:
    """Authorization URL should request identity and guild access by default."""

    http_client = AsyncMock(spec=httpx.AsyncClient)
    client = _build_client(http_client)

    authorization_url = client.build_authorization_url(state="secure-random-state")

    parsed_url = urlparse(authorization_url)
    query = parse_qs(parsed_url.query)

    assert (
        f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        == "https://discord.com/oauth2/authorize"
    )
    assert query["response_type"] == ["code"]
    assert query["client_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [REDIRECT_URI]
    assert query["scope"] == ["identify guilds"]
    assert query["state"] == ["secure-random-state"]
    assert query["prompt"] == ["consent"]


def test_build_authorization_url_supports_verification_scopes_without_prompt() -> None:
    """Member verification should request identify only and skip forced consent."""

    http_client = AsyncMock(spec=httpx.AsyncClient)
    client = _build_client(http_client)

    authorization_url = client.build_authorization_url(
        state="secure-random-state",
        scopes=VERIFICATION_OAUTH_SCOPES,
        prompt=None,
    )

    query = parse_qs(urlparse(authorization_url).query)

    assert query["scope"] == ["identify"]
    assert "prompt" not in query


def test_build_authorization_url_dashboard_scopes_explicit() -> None:
    """Dashboard login should keep identify + guilds scopes."""

    http_client = AsyncMock(spec=httpx.AsyncClient)
    client = _build_client(http_client)

    authorization_url = client.build_authorization_url(
        state="secure-random-state",
        scopes=DASHBOARD_OAUTH_SCOPES,
    )

    query = parse_qs(urlparse(authorization_url).query)

    assert query["scope"] == ["identify guilds"]


@pytest.mark.anyio
async def test_exchange_code_returns_oauth_token() -> None:
    """Authorization code should be exchanged for a typed token."""

    response = _build_response(
        {
            "access_token": ACCESS_TOKEN,
            "token_type": "Bearer",
            "expires_in": 604800,
            "refresh_token": "discord-refresh-token",
            "scope": "identify guilds",
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.return_value = response

    client = _build_client(http_client)

    token = await client.exchange_code(code="discord-authorization-code")

    assert token.access_token == ACCESS_TOKEN
    assert token.token_type == "Bearer"
    assert token.expires_in == 604800
    assert token.refresh_token == "discord-refresh-token"
    assert token.scope == frozenset({"identify", "guilds"})

    http_client.post.assert_awaited_once_with(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": "discord-authorization-code",
            "redirect_uri": REDIRECT_URI,
        },
        auth=(
            CLIENT_ID,
            CLIENT_SECRET,
        ),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )


@pytest.mark.anyio
async def test_get_current_user_returns_discord_identity() -> None:
    """Authenticated Discord identity should be returned."""

    response = _build_response(
        {
            "id": "987654321098765432",
            "username": "norgoth",
            "global_name": "Norgoth",
            "avatar": "avatar-hash",
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)

    user = await client.get_current_user(access_token=ACCESS_TOKEN)

    assert user.id == "987654321098765432"
    assert user.username == "norgoth"
    assert user.global_name == "Norgoth"
    assert user.avatar == "avatar-hash"

    http_client.get.assert_awaited_once_with(
        "https://discord.com/api/v10/users/@me",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
        },
    )


@pytest.mark.anyio
async def test_get_current_user_allows_nullable_profile_fields() -> None:
    """Optional Discord profile fields may be null."""

    response = _build_response(
        {
            "id": "987654321098765432",
            "username": "norgoth",
            "global_name": None,
            "avatar": None,
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)

    user = await client.get_current_user(access_token=ACCESS_TOKEN)

    assert user.global_name is None
    assert user.avatar is None


@pytest.mark.anyio
async def test_get_current_user_guilds_returns_partial_guilds() -> None:
    """Authenticated user guilds should be returned."""

    response = _build_response(
        [
            {
                "id": "111111111111111111",
                "name": "First Guild",
                "owner": True,
                "permissions": "8",
            },
            {
                "id": "222222222222222222",
                "name": "Second Guild",
                "owner": False,
                "permissions": "104324673",
            },
        ]
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)

    guilds = await client.get_current_user_guilds(access_token=ACCESS_TOKEN)

    assert [guild.id for guild in guilds] == [
        "111111111111111111",
        "222222222222222222",
    ]
    assert guilds[0].name == "First Guild"
    assert guilds[0].owner is True
    assert guilds[1].permissions == "104324673"

    http_client.get.assert_awaited_once_with(
        "https://discord.com/api/v10/users/@me/guilds",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
        },
    )


@pytest.mark.anyio
async def test_exchange_code_wraps_http_error() -> None:
    """Discord token request failures should use a stable error."""

    request = httpx.Request(
        "POST",
        "https://discord.com/api/v10/oauth2/token",
    )
    response = httpx.Response(
        401,
        request=request,
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=request,
        response=response,
    )

    client = _build_client(http_client)

    with pytest.raises(
        DiscordOAuthError,
        match="token exchange failed",
    ):
        await client.exchange_code(code="invalid-code")


@pytest.mark.anyio
async def test_get_current_user_rejects_invalid_payload() -> None:
    """Missing Discord user fields should be rejected."""

    response = _build_response(
        {
            "id": "987654321098765432",
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)

    with pytest.raises(
        DiscordOAuthError,
        match="'username'",
    ):
        await client.get_current_user(access_token=ACCESS_TOKEN)


@pytest.mark.anyio
async def test_get_current_user_guilds_coerces_int_permissions_and_skips_bad_entries() -> None:
    """Invalid guild rows are skipped; int permissions are coerced to strings."""

    response = _build_response(
        [
            {
                "id": "111111111111111111",
                "name": "Owned Guild",
                "owner": True,
                "permissions": 8,
            },
            {
                "id": "bad",
                "name": "Broken",
                "owner": "yes",
                "permissions": "8",
            },
            {
                "id": "222222222222222222",
                "name": "Manage Guild",
                "owner": False,
                "permissions": "32",
            },
        ]
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)
    guilds = await client.get_current_user_guilds(access_token=ACCESS_TOKEN)

    assert [guild.id for guild in guilds] == [
        "111111111111111111",
        "222222222222222222",
    ]
    assert guilds[0].permissions == "8"
    assert guilds[0].owner is True


@pytest.mark.anyio
async def test_get_current_user_guilds_maps_unauthorized() -> None:
    """Discord 401 on guilds must surface as DiscordOAuthError with status."""

    response = _build_response({"message": "401: Unauthorized", "code": 0}, status_code=401)
    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response
    client = _build_client(http_client)

    with pytest.raises(DiscordOAuthError) as raised:
        await client.get_current_user_guilds(access_token=ACCESS_TOKEN)

    assert raised.value.http_status == 401


@pytest.mark.anyio
async def test_refresh_access_token_returns_token() -> None:
    """Refresh token grant should return a typed OAuth token."""

    response = _build_response(
        {
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token",
            "scope": "identify guilds",
        }
    )
    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post.return_value = response
    client = _build_client(http_client)

    token = await client.refresh_access_token(refresh_token="old-refresh")

    assert token.access_token == "new-access-token"
    assert token.refresh_token == "new-refresh-token"
    http_client.post.assert_awaited_once()
    assert http_client.post.await_args.kwargs["data"]["grant_type"] == "refresh_token"


@pytest.mark.anyio
async def test_get_current_user_guilds_rejects_invalid_payload() -> None:
    """Guild endpoint should reject non-list response bodies."""

    response = _build_response(
        {
            "id": "not-a-list",
        }
    )

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)

    with pytest.raises(
        DiscordOAuthError,
        match="invalid payload",
    ):
        await client.get_current_user_guilds(access_token=ACCESS_TOKEN)


@pytest.mark.anyio
async def test_get_current_user_rejects_invalid_json() -> None:
    """Malformed JSON responses should be converted to OAuth errors."""

    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.is_success = True
    response.headers = {}
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("Invalid JSON")

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.get.return_value = response

    client = _build_client(http_client)

    with pytest.raises(
        DiscordOAuthError,
        match="invalid JSON",
    ):
        await client.get_current_user(access_token=ACCESS_TOKEN)
