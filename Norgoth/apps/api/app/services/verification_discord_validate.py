"""Validate verification Discord channels/roles against the live guild."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.integrations.discord.bot_rest import (
    CHANNEL_TYPE_ANNOUNCEMENT,
    CHANNEL_TYPE_TEXT,
    DiscordBotAPIError,
    DiscordBotClient,
)
from app.security.discord_effective_permissions import (
    VERIFICATION_CHANNEL_REQUIRED,
    infer_overwrite_scope,
    missing_permission_labels,
    resolve_effective_channel_permissions,
)
from app.security.discord_permissions import (
    ADMINISTRATOR,
    MANAGE_ROLES,
    compute_member_permissions,
)
from app.services.views import ConfigurationView

logger = logging.getLogger(__name__)

TEXT_CHANNEL_TYPES = {CHANNEL_TYPE_TEXT, CHANNEL_TYPE_ANNOUNCEMENT}


@dataclass
class ValidationIssue:
    code: str
    message: str
    field: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    missing_permissions: list[str] | None = None
    overwrite_scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }
        if self.channel_id is not None:
            payload["channel_id"] = self.channel_id
        if self.channel_name is not None:
            payload["channel_name"] = self.channel_name
        if self.missing_permissions is not None:
            payload["missing_permissions"] = self.missing_permissions
        if self.overwrite_scope is not None:
            payload["overwrite_scope"] = self.overwrite_scope
        return payload


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


def _channel_display_name(channel: dict[str, Any], channel_id: str) -> str:
    name = str(channel.get("name") or "").strip()
    return name or channel_id


def _log_channel_permission_diagnostics(
    *,
    guild_id: str,
    channel_id: str,
    channel: dict[str, Any],
    member_role_ids: list[str],
    base_permissions: int,
    effective_permissions: int,
    missing: int,
    category_overwrites: list[dict[str, Any]] | None,
    channel_overwrites: list[dict[str, Any]],
    overwrite_scope: str | None,
) -> None:
    logger.info(
        "verification_channel_permission_check",
        extra={
            "guild_id": guild_id,
            "channel_id": channel_id,
            "channel_type": channel.get("type"),
            "parent_id": channel.get("parent_id"),
            "bot_role_ids": member_role_ids,
            "guild_permission_bits": base_permissions,
            "category_overwrite_count": len(category_overwrites or []),
            "channel_overwrite_count": len(channel_overwrites),
            "effective_permission_bits": effective_permissions,
            "missing_permission_bits": missing,
            "administrator_bypass": bool(base_permissions & ADMINISTRATOR),
            "overwrite_scope": overwrite_scope,
        },
    )


async def _fetch_category_overwrites(
    bot_client: DiscordBotClient,
    *,
    parent_id: str | None,
    guild_id: str,
    field_name: str,
    issues: list[ValidationIssue],
) -> list[dict[str, Any]] | None:
    if not parent_id:
        return None

    try:
        category = await bot_client.get_channel(str(parent_id))
    except DiscordBotAPIError as error:
        status = error.status_code or 0
        if status == 404:
            issues.append(
                ValidationIssue(
                    code="discord_resource_not_in_guild",
                    message=f"Parent category {parent_id} was not found.",
                    field=field_name,
                )
            )
        elif status in {401, 403}:
            issues.append(
                ValidationIssue(
                    code="missing_bot_permissions",
                    message=f"Bot cannot access parent category {parent_id}.",
                    field=field_name,
                )
            )
        elif status == 429:
            issues.append(
                ValidationIssue(
                    code="discord_rate_limited",
                    message=(
                        f"Discord rate-limited while reading category {parent_id}."
                    ),
                    field=field_name,
                )
            )
        elif status >= 500:
            issues.append(
                ValidationIssue(
                    code="discord_unavailable",
                    message=(
                        "Discord is temporarily unavailable while reading "
                        f"category {parent_id}."
                    ),
                    field=field_name,
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    code="guild_metadata_unavailable",
                    message=f"Discord failed while reading category {parent_id}.",
                    field=field_name,
                )
            )
        return None

    if str(category.get("guild_id") or "") != str(guild_id):
        issues.append(
            ValidationIssue(
                code="discord_resource_not_in_guild",
                message=f"Parent category {parent_id} does not belong to this guild.",
                field=field_name,
            )
        )
        return None

    overwrites = category.get("permission_overwrites") or []
    return overwrites if isinstance(overwrites, list) else []


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
    bot_user_id = str(bot_user["id"])
    base_permissions = compute_member_permissions(
        guild_id=discord_guild_id,
        owner_id=None,
        member_user_id=bot_user_id,
        member_roles=member_role_ids,
        roles=roles,
    )
    if not (base_permissions & ADMINISTRATOR) and not (
        base_permissions & MANAGE_ROLES
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
                base_permissions & ADMINISTRATOR
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

        channel_type = _as_int(channel.get("type"))
        if channel_type not in TEXT_CHANNEL_TYPES:
            issues.append(
                ValidationIssue(
                    code="unsupported_verification_channel_type",
                    message=(
                        f"Channel {_channel_display_name(channel, str(channel_id))} "
                        "must be a text or announcement channel."
                    ),
                    field=field_name,
                    channel_id=str(channel_id),
                    channel_name=_channel_display_name(channel, str(channel_id)),
                )
            )
            continue

        channel_overwrites = channel.get("permission_overwrites") or []
        if not isinstance(channel_overwrites, list):
            channel_overwrites = []

        category_overwrites = await _fetch_category_overwrites(
            bot_client,
            parent_id=str(channel.get("parent_id") or "").strip() or None,
            guild_id=discord_guild_id,
            field_name=field_name,
            issues=issues,
        )
        if category_overwrites is None and any(
            issue.field == field_name
            and issue.code
            in {
                "discord_resource_not_in_guild",
                "missing_bot_permissions",
                "discord_rate_limited",
                "discord_unavailable",
                "guild_metadata_unavailable",
            }
            for issue in issues
        ):
            continue

        effective_permissions, admin_bypass = resolve_effective_channel_permissions(
            guild_id=discord_guild_id,
            member_user_id=bot_user_id,
            member_role_ids=member_role_ids,
            roles=roles,
            category_overwrites=category_overwrites,
            channel_overwrites=channel_overwrites,
        )
        if admin_bypass:
            continue

        missing = VERIFICATION_CHANNEL_REQUIRED & ~effective_permissions
        if not missing:
            continue

        channel_name = _channel_display_name(channel, str(channel_id))
        missing_labels = missing_permission_labels(missing)
        overwrite_scope = infer_overwrite_scope(
            base=base_permissions,
            effective=effective_permissions,
            required=VERIFICATION_CHANNEL_REQUIRED,
            category_overwrites=category_overwrites,
            channel_overwrites=channel_overwrites,
            guild_id=discord_guild_id,
            member_user_id=bot_user_id,
            member_role_ids=member_role_ids,
            roles_by_id=roles_by_id,
        )
        _log_channel_permission_diagnostics(
            guild_id=discord_guild_id,
            channel_id=str(channel_id),
            channel=channel,
            member_role_ids=member_role_ids,
            base_permissions=base_permissions,
            effective_permissions=effective_permissions,
            missing=missing,
            category_overwrites=category_overwrites,
            channel_overwrites=channel_overwrites,
            overwrite_scope=overwrite_scope,
        )
        issues.append(
            ValidationIssue(
                code="missing_channel_permissions",
                message=(
                    f"Bot needs {', '.join(missing_labels)} in #{channel_name}."
                ),
                field=field_name,
                channel_id=str(channel_id),
                channel_name=channel_name,
                missing_permissions=missing_labels,
                overwrite_scope=overwrite_scope,
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
