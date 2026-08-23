"""Discord OAuth2 client used by the verification and dashboard flows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

_DISCORD_API_BASE_URL = "https://discord.com/api/v10"
_DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
_DISCORD_TOKEN_URL = f"{_DISCORD_API_BASE_URL}/oauth2/token"
_DISCORD_CURRENT_USER_URL = f"{_DISCORD_API_BASE_URL}/users/@me"
_DISCORD_CURRENT_USER_GUILDS_URL = f"{_DISCORD_API_BASE_URL}/users/@me/guilds"
VERIFICATION_OAUTH_SCOPES = ("identify",)
DASHBOARD_OAUTH_SCOPES = ("identify", "guilds")
_DEFAULT_OAUTH_SCOPES = DASHBOARD_OAUTH_SCOPES

logger = logging.getLogger(__name__)


class DiscordOAuthError(RuntimeError):
    """Raised when Discord OAuth2 communication fails."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        discord_code: int | None = None,
        operation: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.discord_code = discord_code
        self.operation = operation
        self.retry_after = retry_after


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


def token_has_required_scopes(scope: frozenset[str]) -> bool:
    """Return True when the token includes identify and guilds."""

    return "identify" in scope and "guilds" in scope


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
        scopes: tuple[str, ...] | None = None,
        prompt: str | None = "consent",
    ) -> str:
        """Return the Discord authorization URL for the requested OAuth scopes."""

        resolved_scopes = scopes or _DEFAULT_OAUTH_SCOPES
        query_params: dict[str, str] = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri or self._redirect_uri,
            "scope": " ".join(resolved_scopes),
            "state": state,
        }
        if prompt is not None:
            query_params["prompt"] = prompt

        query = urlencode(query_params)

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
        except httpx.HTTPError as error:
            message = "Discord OAuth token exchange failed."
            raise DiscordOAuthError(
                message,
                operation="token_exchange",
            ) from error

        return self._parse_token_response(
            response,
            operation="token_exchange",
        )

    async def refresh_access_token(
        self,
        *,
        refresh_token: str,
    ) -> DiscordOAuthToken:
        """Refresh a Discord access token using a refresh token."""

        try:
            response = await self._http_client.post(
                _DISCORD_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                auth=(
                    self._client_id,
                    self._client_secret,
                ),
                headers={
                    "Content-Type": ("application/x-www-form-urlencoded"),
                },
            )
        except httpx.HTTPError as error:
            message = "Discord OAuth token refresh failed."
            raise DiscordOAuthError(
                message,
                operation="token_refresh",
            ) from error

        return self._parse_token_response(
            response,
            operation="token_refresh",
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
        except httpx.HTTPError as error:
            message = "Discord current-user guild request failed."
            raise DiscordOAuthError(
                message,
                operation="current_user_guilds",
            ) from error

        self._raise_for_discord_response(
            response,
            operation="current_user_guilds",
            failure_message="Discord current-user guild request failed.",
        )

        try:
            payload = response.json()
        except ValueError as error:
            message = "Discord current-user guild request returned invalid JSON."
            raise DiscordOAuthError(
                message,
                http_status=response.status_code,
                operation="current_user_guilds",
            ) from error

        if not isinstance(payload, list):
            message = "Discord current-user guild request returned an invalid payload."
            raise DiscordOAuthError(
                message,
                http_status=response.status_code,
                operation="current_user_guilds",
            )

        guilds: list[DiscordOAuthGuild] = []

        for item in payload:
            parsed = self._try_parse_guild(item)
            if parsed is not None:
                guilds.append(parsed)

        return guilds

    def _parse_token_response(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> DiscordOAuthToken:
        self._raise_for_discord_response(
            response,
            operation=operation,
            failure_message=f"Discord OAuth {operation.replace('_', ' ')} failed.",
        )

        payload = self._read_json_object(
            response,
            operation=f"Discord OAuth {operation}",
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

    def _raise_for_discord_response(
        self,
        response: httpx.Response,
        *,
        operation: str,
        failure_message: str,
    ) -> None:
        if response.is_success:
            return

        discord_code: int | None = None
        retry_after = response.headers.get("Retry-After")
        try:
            body = response.json()
            if isinstance(body, dict):
                raw_code = body.get("code")
                if isinstance(raw_code, int) and not isinstance(raw_code, bool):
                    discord_code = raw_code
        except ValueError:
            pass

        raise DiscordOAuthError(
            failure_message,
            http_status=response.status_code,
            discord_code=discord_code,
            operation=operation,
            retry_after=retry_after,
        )

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
        except httpx.HTTPError as error:
            message = f"{operation} failed."
            raise DiscordOAuthError(
                message,
                operation=operation,
            ) from error

        self._raise_for_discord_response(
            response,
            operation=operation,
            failure_message=f"{operation} failed.",
        )

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
    def _try_parse_guild(item: object) -> DiscordOAuthGuild | None:
        """Parse one guild entry; skip invalid entries instead of failing the list."""

        if not isinstance(item, dict):
            logger.warning("Skipping Discord guild entry that is not an object.")
            return None

        guild_payload = dict(item)
        guild_id = guild_payload.get("id")
        name = guild_payload.get("name")
        if not isinstance(guild_id, str) or not guild_id:
            logger.warning("Skipping Discord guild entry with invalid id.")
            return None
        if not isinstance(name, str) or not name:
            logger.warning(
                "Skipping Discord guild entry with invalid name (id=%s).",
                guild_id,
            )
            return None

        owner_value = guild_payload.get("owner")
        if not isinstance(owner_value, bool):
            logger.warning(
                "Skipping Discord guild entry with invalid owner (id=%s).",
                guild_id,
            )
            return None

        permissions_value = guild_payload.get("permissions")
        if isinstance(permissions_value, bool):
            logger.warning(
                "Skipping Discord guild entry with invalid permissions (id=%s).",
                guild_id,
            )
            return None
        if isinstance(permissions_value, int):
            permissions = str(permissions_value)
        elif isinstance(permissions_value, str) and permissions_value:
            permissions = permissions_value
        else:
            logger.warning(
                "Skipping Discord guild entry with missing permissions (id=%s).",
                guild_id,
            )
            return None

        icon_value = guild_payload.get("icon")
        return DiscordOAuthGuild(
            id=guild_id,
            name=name,
            owner=owner_value,
            permissions=permissions,
            icon=(icon_value if isinstance(icon_value, str) else None),
        )

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
            raise DiscordOAuthError(
                message,
                http_status=response.status_code,
                operation=operation,
            ) from error

        if not isinstance(payload, dict):
            message = f"{operation} returned an invalid payload."
            raise DiscordOAuthError(
                message,
                http_status=response.status_code,
                operation=operation,
            )

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
    "DASHBOARD_OAUTH_SCOPES",
    "DiscordOAuthClient",
    "DiscordOAuthError",
    "DiscordOAuthGuild",
    "DiscordOAuthToken",
    "DiscordOAuthUser",
    "VERIFICATION_OAUTH_SCOPES",
    "token_has_required_scopes",
]
