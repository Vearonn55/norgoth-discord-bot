"""Tests for signed Discord OAuth state values."""

import pytest

from app.security.oauth_state import (
    DiscordOAuthStateService,
    InvalidOAuthStateError,
)

SECRET = "discord-client-secret"
DISCORD_GUILD_ID = "123456789012345678"


def _build_service() -> DiscordOAuthStateService:
    """Create an OAuth state service for tests."""

    return DiscordOAuthStateService(
        secret=SECRET,
        lifetime_seconds=600,
    )


def test_create_and_verify_oauth_state() -> None:
    """A newly created state should preserve its guild ID."""

    service = _build_service()

    state_value = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )

    result = service.verify(
        state_value,
        current_time=1_300,
    )

    assert result.discord_guild_id == DISCORD_GUILD_ID
    assert result.issued_at == 1_000
    assert result.nonce


def test_state_values_use_unique_nonces() -> None:
    """Separate OAuth attempts should not produce identical state values."""

    service = _build_service()

    first_state = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )
    second_state = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )

    assert first_state != second_state


def test_rejects_tampered_oauth_state() -> None:
    """Changing a state value should invalidate its signature."""

    service = _build_service()

    state_value = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )
    encoded_payload, signature = state_value.split(".", maxsplit=1)

    replacement = "A" if encoded_payload[-1] != "A" else "B"
    tampered_payload = f"{encoded_payload[:-1]}{replacement}"

    with pytest.raises(
        InvalidOAuthStateError,
        match="signature",
    ):
        service.verify(
            f"{tampered_payload}.{signature}",
            current_time=1_100,
        )


def test_rejects_expired_oauth_state() -> None:
    """OAuth state should expire after its configured lifetime."""

    service = _build_service()

    state_value = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )

    with pytest.raises(
        InvalidOAuthStateError,
        match="expired",
    ):
        service.verify(
            state_value,
            current_time=1_601,
        )


def test_accepts_state_at_expiration_boundary() -> None:
    """OAuth state should remain valid at the exact lifetime boundary."""

    service = _build_service()

    state_value = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )

    result = service.verify(
        state_value,
        current_time=1_600,
    )

    assert result.discord_guild_id == DISCORD_GUILD_ID


def test_rejects_invalid_discord_guild_id() -> None:
    """State creation should reject invalid Discord guild IDs."""

    service = _build_service()

    with pytest.raises(
        ValueError,
        match="1 to 20 digits",
    ):
        service.create(
            discord_guild_id="invalid-guild",
            current_time=1_000,
        )


def test_rejects_state_with_future_issue_time() -> None:
    """An OAuth state issued too far in the future should be rejected."""

    service = _build_service()

    state_value = service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=2_000,
    )

    with pytest.raises(
        InvalidOAuthStateError,
        match="issue time",
    ):
        service.verify(
            state_value,
            current_time=1_000,
        )


def test_rejects_state_signed_with_different_secret() -> None:
    """A different application secret must not validate the state."""

    first_service = _build_service()
    second_service = DiscordOAuthStateService(
        secret="different-secret",
        lifetime_seconds=600,
    )

    state_value = first_service.create(
        discord_guild_id=DISCORD_GUILD_ID,
        current_time=1_000,
    )

    with pytest.raises(
        InvalidOAuthStateError,
        match="signature",
    ):
        second_service.verify(
            state_value,
            current_time=1_100,
        )


def test_create_and_verify_display_context() -> None:
    service = _build_service()
    token = service.create_display_context(
        guild_id=DISCORD_GUILD_ID,
        guild_name="Norgoth Guild",
        guild_icon_url="https://cdn.discordapp.com/icons/1/abc.png?size=128",
        lang="tr",
        current_time=1_000,
    )
    context = service.verify_display_context(token, current_time=1_200)
    assert context.guild_id == DISCORD_GUILD_ID
    assert context.guild_name == "Norgoth Guild"
    assert context.guild_icon_url == "https://cdn.discordapp.com/icons/1/abc.png?size=128"
    assert context.lang == "tr"


def test_rejects_tampered_display_context() -> None:
    service = _build_service()
    token = service.create_display_context(
        guild_id=DISCORD_GUILD_ID,
        guild_name="Guild",
        guild_icon_url=None,
        lang="en",
        current_time=1_000,
    )
    encoded_payload, signature = token.split(".", maxsplit=1)
    replacement = "A" if encoded_payload[-1] != "A" else "B"
    tampered = f"{encoded_payload[:-1]}{replacement}.{signature}"
    with pytest.raises(InvalidOAuthStateError, match="signature"):
        service.verify_display_context(tampered, current_time=1_100)
