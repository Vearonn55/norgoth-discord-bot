"""Validate verification Discord channels/roles against the live guild."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.services.views import ConfigurationView

PERM_ADMINISTRATOR = 1 << 3
PERM_VIEW_CHANNEL = 1 << 10
PERM_SEND_MESSAGES = 1 << 11
PERM_MANAGE_ROLES = 1 << 28
PERM_EMBED_LINKS = 1 << 14
PERM_READ_MESSAGE_HISTORY = 1 << 16

CHANNEL_REQUIRED = (
    PERM_VIEW_CHANNEL
    | PERM_SEND_MESSAGES
    | PERM_EMBED_LINKS
    | PERM_READ_MESSAGE_HISTORY
)


@dataclass
class ValidationIssue:
    code: str
    message: str
    field: str | None = None


@dataclass
class VerificationDiscordValidation:
    ok: bool
    setup_state: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def primary_code(self) -> str | None:
        return self.issues[0].code if self.issues else None


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _role_map(roles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(role.get("id")): role for role in roles if role.get("id")}


def _compute_base_permissions(
    *,
    guild_id: str,
    member_role_ids: list[str],
    roles_by_id: dict[str, dict[str, Any]],
) -> int:
    everyone = roles_by_id.get(str(guild_id))
    permissions = _as_int(everyone.get("permissions") if everyone else 0)
    for role_id in member_role_ids:
        role = roles_by_id.get(str(role_id))
        if role is None:
            continue
        permissions |= _as_int(role.get("permissions"))
    return permissions


def _apply_overwrites(
    base: int,
    *,
    guild_id: str,
    member_id: str,
    member_role_ids: list[str],
    overwrites: list[dict[str, Any]],
) -> int:
    permissions = base
    everyone_ow = next(
        (ow for ow in overwrites if str(ow.get("id")) == str(guild_id)),
        None,
    )
    if everyone_ow is not None:
        permissions &= ~_as_int(everyone_ow.get("deny"))
        permissions |= _as_int(everyone_ow.get("allow"))

    allow = 0
    deny = 0
    for role_id in member_role_ids:
        ow = next((item for item in overwrites if str(item.get("id")) == str(role_id)), None)
        if ow is None:
            continue
        allow |= _as_int(ow.get("allow"))
        deny |= _as_int(ow.get("deny"))
    permissions &= ~deny
    permissions |= allow

    member_ow = next(
        (ow for ow in overwrites if str(ow.get("id")) == str(member_id)),
        None,
    )
    if member_ow is not None:
        permissions &= ~_as_int(member_ow.get("deny"))
        permissions |= _as_int(member_ow.get("allow"))
    return permissions


def _highest_bot_position(
    *,
    guild_id: str,
    member_role_ids: list[str],
    roles_by_id: dict[str, dict[str, Any]],
) -> int:
    highest = 0
    for role_id in member_role_ids:
        if str(role_id) == str(guild_id):
            continue
        role = roles_by_id.get(str(role_id))
        if role is None:
            continue
        highest = max(highest, _as_int(role.get("position")))
    return highest


async def validate_verification_discord_resources(
    *,
    bot_client: DiscordBotClient,
    discord_guild_id: str,
    configuration: ConfigurationView,
) -> VerificationDiscordValidation:
    """Check channels/roles belong to the guild and bot can manage them."""

    issues: list[ValidationIssue] = []

    try:
        roles = await bot_client.list_guild_roles(discord_guild_id)
        bot_user = await bot_client.get_bot_user()
        bot_member = await bot_client.get_guild_member(
            discord_guild_id,
            str(bot_user["id"]),
        )
    except DiscordBotAPIError as error:
        status = error.status_code or 0
        if status in {401, 403}:
            return VerificationDiscordValidation(
                ok=False,
                setup_state="error",
                issues=[
                    ValidationIssue(
                        code="missing_bot_permissions",
                        message="Bot cannot read guild roles or membership.",
                    )
                ],
            )
        if status == 404:
            return VerificationDiscordValidation(
                ok=False,
                setup_state="degraded",
                issues=[
                    ValidationIssue(
                        code="bot_not_installed",
                        message="NorBot is not installed in this server.",
                    )
                ],
            )
        if status == 429:
            return VerificationDiscordValidation(
                ok=False,
                setup_state="error",
                issues=[
                    ValidationIssue(
                        code="discord_rate_limited",
                        message="Discord rate-limited this validation request.",
                    )
                ],
            )
        if status >= 500:
            return VerificationDiscordValidation(
                ok=False,
                setup_state="error",
                issues=[
                    ValidationIssue(
                        code="discord_unavailable",
                        message="Discord is temporarily unavailable.",
                    )
                ],
            )
        return VerificationDiscordValidation(
            ok=False,
            setup_state="error",
            issues=[
                ValidationIssue(
                    code="guild_metadata_unavailable",
                    message="Discord could not validate verification resources.",
                )
            ],
        )

    roles_by_id = _role_map(roles)
    member_role_ids = [str(role_id) for role_id in (bot_member.get("roles") or [])]
    base_permissions = _compute_base_permissions(
        guild_id=discord_guild_id,
        member_role_ids=member_role_ids,
        roles_by_id=roles_by_id,
    )
    if not (base_permissions & PERM_ADMINISTRATOR) and not (
        base_permissions & PERM_MANAGE_ROLES
    ):
        issues.append(
            ValidationIssue(
                code="missing_bot_permissions",
                message="Bot is missing the Manage Roles permission.",
            )
        )

    bot_top = _highest_bot_position(
        guild_id=discord_guild_id,
        member_role_ids=member_role_ids,
        roles_by_id=roles_by_id,
    )

    role_fields = {
        "unverified_role_id": configuration.unverified_role_id,
        "member_role_id": configuration.member_role_id,
    }
    if configuration.manual_review_role_id:
        role_fields["manual_review_role_id"] = configuration.manual_review_role_id

    for field_name, role_id in role_fields.items():
        role = roles_by_id.get(str(role_id))
        if role is None:
            issues.append(
                ValidationIssue(
                    code="discord_resource_not_in_guild",
                    message=f"Role {role_id} is not in this guild.",
                    field=field_name,
                )
            )
            continue
        if role.get("managed"):
            issues.append(
                ValidationIssue(
                    code="role_managed",
                    message=f"Role {role_id} is managed and cannot be assigned by the bot.",
                    field=field_name,
                )
            )
            continue
        if field_name in {"unverified_role_id", "member_role_id"}:
            if _as_int(role.get("position")) >= bot_top and not (
                base_permissions & PERM_ADMINISTRATOR
            ):
                issues.append(
                    ValidationIssue(
                        code="role_hierarchy_invalid",
                        message=(
                            f"Bot role must be above the configured {field_name.replace('_', ' ')}."
                        ),
                        field=field_name,
                    )
                )

    for field_name, channel_id in (
        ("verification_channel_id", configuration.verification_channel_id),
        *(
            (("log_channel_id", configuration.log_channel_id),)
            if str(configuration.log_channel_id or "").strip()
            else ()
        ),
    ):
        try:
            channel = await bot_client.get_channel(str(channel_id))
        except DiscordBotAPIError as error:
            status = error.status_code or 0
            if status == 404:
                issues.append(
                    ValidationIssue(
                        code="discord_resource_not_in_guild",
                        message=f"Channel {channel_id} was not found.",
                        field=field_name,
                    )
                )
            elif status in {401, 403}:
                issues.append(
                    ValidationIssue(
                        code="missing_bot_permissions",
                        message=f"Bot cannot access channel {channel_id}.",
                        field=field_name,
                    )
                )
            elif status == 429:
                issues.append(
                    ValidationIssue(
                        code="discord_rate_limited",
                        message=f"Discord rate-limited while reading channel {channel_id}.",
                        field=field_name,
                    )
                )
            elif status >= 500:
                issues.append(
                    ValidationIssue(
                        code="discord_unavailable",
                        message=f"Discord is temporarily unavailable while reading channel {channel_id}.",
                        field=field_name,
                    )
                )
            else:
                issues.append(
                    ValidationIssue(
                        code="guild_metadata_unavailable",
                        message=f"Discord failed while reading channel {channel_id}.",
                        field=field_name,
                    )
                )
            continue

        if str(channel.get("guild_id") or "") != str(discord_guild_id):
            issues.append(
                ValidationIssue(
                    code="discord_resource_not_in_guild",
                    message=f"Channel {channel_id} does not belong to this guild.",
                    field=field_name,
                )
            )
            continue

        overwrites = channel.get("permission_overwrites") or []
        if not isinstance(overwrites, list):
            overwrites = []
        channel_perms = _apply_overwrites(
            base_permissions,
            guild_id=discord_guild_id,
            member_id=str(bot_user["id"]),
            member_role_ids=member_role_ids,
            overwrites=overwrites,
        )
        if base_permissions & PERM_ADMINISTRATOR:
            continue
        missing = CHANNEL_REQUIRED & ~channel_perms
        if missing:
            issues.append(
                ValidationIssue(
                    code="missing_bot_permissions",
                    message=(
                        f"Bot needs View Channel, Send Messages, Embed Links, "
                        f"and Read Message History in {field_name.replace('_', ' ')}."
                    ),
                    field=field_name,
                )
            )

    if issues:
        codes = {issue.code for issue in issues}
        if codes & {
            "guild_metadata_unavailable",
            "discord_unavailable",
            "discord_rate_limited",
        }:
            setup_state = "error"
        else:
            setup_state = "degraded"
        return VerificationDiscordValidation(
            ok=False,
            setup_state=setup_state,
            issues=issues,
        )

    return VerificationDiscordValidation(ok=True, setup_state="active", issues=[])
