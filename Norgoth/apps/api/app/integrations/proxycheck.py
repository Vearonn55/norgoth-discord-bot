"""proxycheck.io VPN and proxy detection integration."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

_PROXYCHECK_API_BASE_URL = "https://proxycheck.io/v3"
_PROXYCHECK_API_VERSION = "24-June-2026"


class ProxycheckError(RuntimeError):
    """Raised when a proxycheck.io lookup cannot be completed."""


class InvalidProxycheckIPAddressError(ValueError):
    """Raised when a supplied IP address is invalid."""


@dataclass(frozen=True, slots=True)
class ProxycheckResult:
    """Normalized result from one proxycheck.io IP lookup."""

    ip_address: str
    anonymous: bool
    status: str

    @property
    def vpn_or_proxy_detected(self) -> bool:
        """Return whether the address is anonymous."""

        return self.anonymous


class ProxycheckClient:
    """Check IP addresses through the proxycheck.io v3 API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        api_key: str | None = None,
    ) -> None:
        """Initialize the proxycheck.io client."""

        normalized_api_key = api_key.strip() if api_key is not None else None

        self._http_client = http_client
        self._api_key = normalized_api_key or None

    async def check_ip(
        self,
        ip_address: str,
    ) -> ProxycheckResult:
        """Return the VPN and proxy detection result for an IP."""

        normalized_ip = self._normalize_ip(ip_address)
        encoded_ip = quote(normalized_ip, safe="")

        query_parameters = {
            "p": "0",
            "tag": "0",
            "ver": _PROXYCHECK_API_VERSION,
        }

        if self._api_key is not None:
            query_parameters["key"] = self._api_key

        try:
            response = await self._http_client.get(
                f"{_PROXYCHECK_API_BASE_URL}/{encoded_ip}",
                params=query_parameters,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            message = "proxycheck.io IP lookup failed."
            raise ProxycheckError(message) from error

        payload = self._read_json_object(response)
        response_status = self._read_status(payload)

        if response_status not in {"ok", "warning"}:
            optional_message = self._read_optional_message(payload)
            detail = (
                f"proxycheck.io rejected the IP lookup: {optional_message}"
                if optional_message is not None
                else "proxycheck.io rejected the IP lookup."
            )
            raise ProxycheckError(detail)

        result_key = payload.get("ip")

        if not isinstance(result_key, str) or not result_key:
            result_key = normalized_ip

        result_payload = payload.get(result_key)

        if not isinstance(result_payload, dict):
            message = "proxycheck.io returned an invalid IP result payload."
            raise ProxycheckError(message)

        detections = result_payload.get("detections")

        if not isinstance(detections, dict):
            message = "proxycheck.io returned an invalid detections payload."
            raise ProxycheckError(message)

        anonymous = detections.get("anonymous")

        if not isinstance(anonymous, bool):
            message = "proxycheck.io returned an invalid anonymous result."
            raise ProxycheckError(message)

        return ProxycheckResult(
            ip_address=normalized_ip,
            anonymous=anonymous,
            status=response_status,
        )

    @staticmethod
    def _normalize_ip(ip_address: str) -> str:
        """Validate and normalize an IPv4 or IPv6 address."""

        try:
            return ipaddress.ip_address(ip_address.strip()).compressed
        except ValueError as error:
            message = "A valid IPv4 or IPv6 address is required."
            raise InvalidProxycheckIPAddressError(message) from error

    @staticmethod
    def _read_json_object(
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Return the response body as a JSON object."""

        try:
            payload = response.json()
        except ValueError as error:
            message = "proxycheck.io returned invalid JSON."
            raise ProxycheckError(message) from error

        if not isinstance(payload, dict):
            message = "proxycheck.io returned an invalid response payload."
            raise ProxycheckError(message)

        return dict(payload)

    @staticmethod
    def _read_status(payload: dict[str, Any]) -> str:
        """Return the API response status."""

        value = payload.get("status")

        if not isinstance(value, str) or not value:
            message = "proxycheck.io response is missing a valid status."
            raise ProxycheckError(message)

        return value.strip().lower()

    @staticmethod
    def _read_optional_message(
        payload: dict[str, Any],
    ) -> str | None:
        """Return an optional API error or warning message."""

        value = payload.get("message")

        if not isinstance(value, str):
            return None

        normalized_value = value.strip()

        return normalized_value or None


__all__ = [
    "InvalidProxycheckIPAddressError",
    "ProxycheckClient",
    "ProxycheckError",
    "ProxycheckResult",
]
