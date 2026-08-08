"""Discord OAuth2 client used by the verification flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

_DISCORD_API_BASE_URL = "https://discord.com/api/v10"
_DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
_DISCORD_TOKEN_URL = f"{_DISCORD_API_BASE_URL}/oauth2/token"
_DISCORD_CURRENT_USER_URL = f"{_DISCORD_API_BASE_URL}/users/@me"
_DISCORD_CURRENT_USER_GUILDS_URL = f"{_DISCORD_API_BASE_URL}/users/@me/guilds"
_DISCORD_OAUTH_SCOPES = ("identify", "guilds")


class DiscordOAuthError(RuntimeError):
    """Raised when Discord OAuth2 communication fails."""


@dataclass(frozen=True, slots=True)
class DiscordOAuthToken:
    """Access token returned by Discord OAuth2."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None
    scope: frozenset[str]


@dataclass(frozen=True, slots=True)
class DiscordOAuthUser:
    """Discord user identity returned by the current-user endpoint."""

    id: str
    username: str
    global_name: str | None
    avatar: str | None


@dataclass(frozen=True, slots=True)
class DiscordOAuthGuild:
    """Partial Discord guild returned for the authenticated user."""

    id: str
    name: str
    owner: bool
    permissions: str
    icon: str | None = None


class DiscordOAuthClient:
    """Exchange Discord OAuth codes and retrieve verification data."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http_client: httpx.AsyncClient,
    ) -> None:
        """Initialize the Discord OAuth2 client."""

        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http_client = http_client

    @property
    def client_id(self) -> str:
        return self._client_id

    def build_authorization_url(
        self,
        *,
        state: str,
        redirect_uri: str | None = None,
    ) -> str:
        """Return the Discord authorization URL for verification."""

        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": redirect_uri or self._redirect_uri,
                "scope": " ".join(_DISCORD_OAUTH_SCOPES),
                "state": state,
                "prompt": "consent",
            }
        )

        return f"{_DISCORD_AUTHORIZE_URL}?{query}"

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str | None = None,
    ) -> DiscordOAuthToken:
        """Exchange an authorization code for a Discord access token."""

        try:
            response = await self._http_client.post(
                _DISCORD_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri or self._redirect_uri,
                },
                auth=(
                    self._client_id,
                    self._client_secret,
                ),
                headers={
                    "Content-Type": ("application/x-www-form-urlencoded"),
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = "Discord OAuth token exchange failed."
            raise DiscordOAuthError(message) from error

        payload = self._read_json_object(
            response,
            operation="Discord OAuth token exchange",
        )

        access_token = self._read_required_string(
            payload,
            "access_token",
        )
        token_type = self._read_required_string(
            payload,
            "token_type",
        )
        expires_in = self._read_required_integer(
            payload,
            "expires_in",
        )
        scope_value = self._read_required_string(
            payload,
            "scope",
        )

        refresh_token_value = payload.get("refresh_token")
        refresh_token = refresh_token_value if isinstance(refresh_token_value, str) else None

        return DiscordOAuthToken(
            access_token=access_token,
            token_type=token_type,
            expires_in=expires_in,
            refresh_token=refresh_token,
            scope=frozenset(scope_value.split()),
        )

    async def get_current_user(
        self,
        *,
        access_token: str,
    ) -> DiscordOAuthUser:
        """Return the Discord identity associated with an access token."""

        payload = await self._get_authorized_json_object(
            url=_DISCORD_CURRENT_USER_URL,
            access_token=access_token,
            operation="Discord current-user request",
        )

        global_name_value = payload.get("global_name")
        avatar_value = payload.get("avatar")

        return DiscordOAuthUser(
            id=self._read_required_string(payload, "id"),
            username=self._read_required_string(
                payload,
                "username",
            ),
            global_name=(global_name_value if isinstance(global_name_value, str) else None),
            avatar=(avatar_value if isinstance(avatar_value, str) else None),
        )

    async def get_current_user_guilds(
        self,
        *,
        access_token: str,
    ) -> list[DiscordOAuthGuild]:
        """Return guilds belonging to the authenticated Discord user."""

        try:
            response = await self._http_client.get(
                _DISCORD_CURRENT_USER_GUILDS_URL,
                headers=self._authorization_headers(access_token),
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = "Discord current-user guild request failed."
            raise DiscordOAuthError(message) from error

        try:
            payload = response.json()
        except ValueError as error:
            message = "Discord current-user guild request returned invalid JSON."
            raise DiscordOAuthError(message) from error

        if not isinstance(payload, list):
            message = "Discord current-user guild request returned an invalid payload."
            raise DiscordOAuthError(message)

        guilds: list[DiscordOAuthGuild] = []

        for item in payload:
            if not isinstance(item, dict):
                message = "Discord current-user guild request returned an invalid guild entry."
                raise DiscordOAuthError(message)

            guild_payload = dict(item)

            owner_value = guild_payload.get("owner")
            permissions_value = guild_payload.get("permissions")

            if not isinstance(owner_value, bool):
                message = "Discord guild payload is missing a valid owner value."
                raise DiscordOAuthError(message)

            if not isinstance(permissions_value, str):
                message = "Discord guild payload is missing valid permissions."
                raise DiscordOAuthError(message)

            icon_value = guild_payload.get("icon")
            guilds.append(
                DiscordOAuthGuild(
                    id=self._read_required_string(
                        guild_payload,
                        "id",
                    ),
                    name=self._read_required_string(
                        guild_payload,
                        "name",
                    ),
                    owner=owner_value,
                    permissions=permissions_value,
                    icon=(icon_value if isinstance(icon_value, str) else None),
                )
            )

        return guilds

    async def _get_authorized_json_object(
        self,
        *,
        url: str,
        access_token: str,
        operation: str,
    ) -> dict[str, Any]:
        """Perform an authorized Discord request returning an object."""

        try:
            response = await self._http_client.get(
                url,
                headers=self._authorization_headers(access_token),
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = f"{operation} failed."
            raise DiscordOAuthError(message) from error

        return self._read_json_object(
            response,
            operation=operation,
        )

    @staticmethod
    def _authorization_headers(
        access_token: str,
    ) -> dict[str, str]:
        """Return OAuth bearer authorization headers."""

        return {
            "Authorization": f"Bearer {access_token}",
        }

    @staticmethod
    def _read_json_object(
        response: httpx.Response,
        *,
        operation: str,
    ) -> dict[str, Any]:
        """Return a JSON response body validated as an object."""

        try:
            payload = response.json()
        except ValueError as error:
            message = f"{operation} returned invalid JSON."
            raise DiscordOAuthError(message) from error

        if not isinstance(payload, dict):
            message = f"{operation} returned an invalid payload."
            raise DiscordOAuthError(message)

        return dict(payload)

    @staticmethod
    def _read_required_string(
        payload: dict[str, Any],
        field_name: str,
    ) -> str:
        """Return a required non-empty string field."""

        value = payload.get(field_name)

        if not isinstance(value, str) or not value:
            message = f"Discord payload is missing a valid {field_name!r}."
            raise DiscordOAuthError(message)

        return value

    @staticmethod
    def _read_required_integer(
        payload: dict[str, Any],
        field_name: str,
    ) -> int:
        """Return a required integer field."""

        value = payload.get(field_name)

        if not isinstance(value, int) or isinstance(value, bool):
            message = f"Discord payload is missing a valid {field_name!r}."
            raise DiscordOAuthError(message)

        return value


__all__ = [
    "DiscordOAuthClient",
    "DiscordOAuthError",
    "DiscordOAuthGuild",
    "DiscordOAuthToken",
    "DiscordOAuthUser",
]
