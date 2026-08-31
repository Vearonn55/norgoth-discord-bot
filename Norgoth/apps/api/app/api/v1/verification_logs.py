"""Version 1 API endpoints for Discord verification logs and manual review."""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.v1.dependencies import (
    ConfigurationServiceDependency,
    DatabaseSession,
    DiscordBotClientDependency,
    GuildServiceDependency,
    HighRiskGuildServiceDependency,
    SettingsDependency,
    VerificationLogServiceDependency,
)
from app.api.v1.dependencies_auth import (
    OperatorSessionDependency,
    guild_manager_dependency,
)
from app.integrations.discord.bot_rest import DiscordBotAPIError, DiscordBotClient
from app.models.enums import VerificationStatus
from app.schemas.review_evidence import ReviewEvidence
from app.schemas.verification_log import (
    BannedAccountEvidence,
    MatchedHighRiskServer,
    VerificationLogDetailResponse,
    VerificationLogListResponse,
    VerificationLogResponse,
    VerificationReviewRequest,
)
from app.services.verification_manual_review_embed import (
    build_manual_verification_dashboard_url,
)
from app.services.verification_review_reasons import derive_manual_review_reason_codes
from app.services.audit import record_audit
from app.services.campaign_store import get_redis
from app.services.logging_presentation import (
    apply_log_title_emoji,
    filter_log_embed_fields,
)
from app.services.verification_log_routing import resolve_verification_log_channel
from app.services.views import VerificationAttemptView

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/guilds/{discord_guild_id}/verification-logs",
    tags=["verification-logs"],
    # Verification history and manual review are moderator-only surfaces.
    dependencies=[Depends(guild_manager_dependency("discord_guild_id"))],
)

DiscordGuildIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]

AttemptIdPath = Annotated[UUID, Path()]

VerificationLogLimitQuery = Annotated[int, Query(ge=1, le=100)]
VerificationLogOffsetQuery = Annotated[int, Query(ge=0)]
VerificationLogSearchQuery = Annotated[str | None, Query(max_length=100)]

VerificationStatusQuery = Annotated[
    VerificationStatus | None,
    Query(alias="status"),
]


def _guild_members_key(discord_guild_id: str) -> str:
    return f"norgoth:guild:{discord_guild_id}:members"


async def _resolve_identities(
    discord_guild_id: str,
    user_ids: set[str],
) -> dict[str, dict[str, str | None]]:
    """Best-effort resolve display name / username / avatar for user IDs.

    Reads the bot's member snapshot from Redis (no per-user Discord API calls)
    so the queue stays cheap. The Discord user ID remains authoritative; this
    is a presentation cache only and degrades gracefully on any failure.
    """

    if not user_ids:
        return {}

    try:
        redis_client = await get_redis()
    except Exception:  # noqa: BLE001 - identity is best-effort only
        return {}

    try:
        raw_members = await redis_client.get(_guild_members_key(discord_guild_id))
    except Exception:  # noqa: BLE001
        raw_members = None
    finally:
        await redis_client.aclose()

    identities: dict[str, dict[str, str | None]] = {}

    if not raw_members:
        return identities

    try:
        snapshot = json.loads(raw_members)
    except (json.JSONDecodeError, TypeError):
        return identities

    for member in snapshot.get("members", []):
        member_id = str(member.get("id"))
        if member_id not in user_ids:
            continue
        display_name = (
            member.get("display_name")
            or member.get("global_name")
            or member.get("name")
        )
        identities[member_id] = {
            "display_name": str(display_name) if display_name else None,
            "username": str(member.get("name")) if member.get("name") else None,
            "avatar_url": (
                str(member.get("avatar_url"))
                if member.get("avatar_url")
                else None
            ),
        }

    return identities


def _to_response(
    view: VerificationAttemptView,
    identity: dict[str, str | None] | None,
) -> VerificationLogResponse:
    """Build a log response, layering best-effort identity on the DB view."""

    identity = identity or {}
    return VerificationLogResponse(
        id=view.id,
        guild_id=view.guild_id,
        discord_user_id=view.discord_user_id,
        display_name=identity.get("display_name"),
        username=identity.get("username"),
        avatar_url=identity.get("avatar_url"),
        status=view.status,
        reason=view.reason,
        vpn_or_proxy_detected=view.vpn_or_proxy_detected,
        shared_ip_detected=view.shared_ip_detected,
        high_risk_guild_detected=view.high_risk_guild_detected,
        matched_high_risk_guild_ids=list(view.matched_high_risk_guild_ids),
        banned_ip_match_detected=view.banned_ip_match_detected,
        reviewed_by=view.reviewed_by,
        reviewed_at=view.reviewed_at,
        created_at=view.created_at,
    )


@router.get(
    "",
    response_model=VerificationLogListResponse,
)
async def list_verification_logs(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
    verification_log_service: VerificationLogServiceDependency,
    limit: VerificationLogLimitQuery = 50,
    offset: VerificationLogOffsetQuery = 0,
    q: VerificationLogSearchQuery = None,
    status_filter: VerificationStatusQuery = None,
) -> VerificationLogListResponse:
    """Return a paginated page of verification attempts for a guild.

    Supports server-side pagination (``limit``/``offset``), a free-text search
    (``q`` matches Discord user ID or cached username) and a ``status`` filter
    (e.g. ``manual_review`` for the review queue). Returns a ``total`` count for
    the active filters so the client can paginate.
    """

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    views, total = await verification_log_service.list_page(
        guild_id=guild.id,
        limit=limit,
        offset=offset,
        status=status_filter,
        query=q,
    )

    identities = await _resolve_identities(
        discord_guild_id,
        {view.discord_user_id for view in views},
    )

    return VerificationLogListResponse(
        items=[
            _to_response(view, identities.get(view.discord_user_id))
            for view in views
        ],
        total=total,
    )


@router.get(
    "/{attempt_id}",
    response_model=VerificationLogDetailResponse,
)
async def get_verification_log(
    discord_guild_id: DiscordGuildIdPath,
    attempt_id: AttemptIdPath,
    guild_service: GuildServiceDependency,
    verification_log_service: VerificationLogServiceDependency,
    high_risk_guild_service: HighRiskGuildServiceDependency,
) -> VerificationLogDetailResponse:
    """Return a single verification attempt as a read-only transcript.

    Resolves the matched High Risk Servers (id + configured reason) so a
    reviewer sees the explicit trigger. Never exposes IP data.
    """

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    view = await verification_log_service.get_attempt(
        guild_id=guild.id,
        attempt_id=attempt_id,
    )

    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification attempt not found.",
        )

    identities = await _resolve_identities(
        discord_guild_id,
        {view.discord_user_id},
    )
    base = _to_response(view, identities.get(view.discord_user_id))

    evidence: ReviewEvidence | None = None
    if view.review_evidence:
        try:
            evidence = ReviewEvidence.model_validate(view.review_evidence)
        except Exception:  # noqa: BLE001
            evidence = None

    matched_servers: list[MatchedHighRiskServer] = []
    matched_banned_accounts: list[BannedAccountEvidence] = []
    proxy_classification: str | None = None
    review_reasons: list[str] = []

    if evidence is not None:
        matched_servers = [
            MatchedHighRiskServer(
                discord_guild_id=server.discord_guild_id,
                reason=server.description,
            )
            for server in evidence.matched_high_risk_servers
        ]
        matched_banned_accounts = [
            BannedAccountEvidence(
                discord_user_id=account.discord_user_id,
                display_name=account.display_name,
                username=account.username,
                source=account.source,
                resolved_at=account.resolved_at,
            )
            for account in evidence.matched_banned_accounts
        ]
        proxy_classification = evidence.proxy_classification
        review_reasons = list(evidence.reasons)
    elif view.matched_high_risk_guild_ids:
        entries = await high_risk_guild_service.list_entries(guild.id)
        reason_by_id = {
            entry.high_risk_discord_guild_id: entry.reason for entry in entries
        }
        matched_servers = [
            MatchedHighRiskServer(
                discord_guild_id=guild_id,
                reason=reason_by_id.get(guild_id),
            )
            for guild_id in view.matched_high_risk_guild_ids
        ]

    if not review_reasons:
        review_reasons = derive_manual_review_reason_codes(
            vpn_or_proxy_detected=view.vpn_or_proxy_detected,
            shared_ip_detected=view.shared_ip_detected,
            banned_ip_match_detected=view.banned_ip_match_detected,
            high_risk_guild_detected=view.high_risk_guild_detected,
            membership_check_unavailable=view.reason
            == "membership_check_unavailable",
            risk_provider_unavailable=view.reason == "risk_provider_unavailable",
        )

    return VerificationLogDetailResponse(
        **base.model_dump(),
        matched_high_risk_servers=matched_servers,
        matched_banned_accounts=matched_banned_accounts,
        review_reasons=review_reasons,
        proxy_classification=proxy_classification,
    )


@router.post(
    "/{attempt_id}/review",
    response_model=VerificationLogResponse,
)
async def review_verification_attempt(
    discord_guild_id: DiscordGuildIdPath,
    attempt_id: AttemptIdPath,
    payload: VerificationReviewRequest,
    guild_service: GuildServiceDependency,
    verification_log_service: VerificationLogServiceDependency,
    configuration_service: ConfigurationServiceDependency,
    bot_client: DiscordBotClientDependency,
    settings: SettingsDependency,
    session: DatabaseSession,
    operator: OperatorSessionDependency,
) -> VerificationLogResponse:
    """Approve or reject a verification attempt held for manual review.

    Concurrency is protected by an atomic conditional update: only the first
    reviewer to act wins; a second concurrent decision receives ``409``.
    Approving grants the Verified + Normal Member roles and removes Unverified;
    rejecting keeps the member on Unverified. The decision, reviewer and time
    are persisted, audit-logged, and posted to the verification log channel with
    a deep link to the read-only transcript.
    """

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    attempt = await verification_log_service.get_attempt(
        guild_id=guild.id,
        attempt_id=attempt_id,
    )

    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification attempt not found.",
        )

    if attempt.status is not VerificationStatus.MANUAL_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This verification attempt is not awaiting manual review.",
        )

    # Atomically claim the review before any external side effects so two
    # concurrent reviewers cannot both apply roles / post logs.
    resolved = await verification_log_service.resolve_manual_review(
        guild_id=guild.id,
        attempt_id=attempt_id,
        approved=payload.approved,
        reviewer_discord_id=operator.user_id,
    )

    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This verification attempt has already been reviewed.",
        )

    configuration = await configuration_service.get_by_guild_id(guild.id)

    if bot_client is not None and configuration is not None:
        await _apply_review_roles(
            bot_client=bot_client,
            discord_guild_id=discord_guild_id,
            discord_user_id=attempt.discord_user_id,
            approved=payload.approved,
            unverified_role_id=configuration.unverified_role_id,
            member_role_id=configuration.member_role_id,
        )

        await _send_manual_review_decision(
            bot_client=bot_client,
            discord_guild_id=discord_guild_id,
            legacy_log_channel_id=configuration.log_channel_id,
            attempt_id=attempt_id,
            discord_user_id=attempt.discord_user_id,
            reviewer_discord_id=operator.user_id,
            approved=payload.approved,
            transcript_url=_build_transcript_url(
                dashboard_public_url=settings.dashboard_public_url,
                discord_guild_id=discord_guild_id,
                attempt_id=attempt_id,
            ),
        )

    await record_audit(
        session,
        entity_type="verification_manual_review",
        action="approve" if payload.approved else "reject",
        guild_id=discord_guild_id,
        entity_id=attempt.discord_user_id,
        changes={
            "actor_discord_id": operator.user_id,
            "attempt_id": str(attempt_id),
            "approved": payload.approved,
        },
    )

    await session.commit()

    identities = await _resolve_identities(
        discord_guild_id,
        {resolved.discord_user_id},
    )

    return _to_response(resolved, identities.get(resolved.discord_user_id))


def _build_transcript_url(
    *,
    dashboard_public_url: str | None,
    discord_guild_id: str,
    attempt_id: UUID,
) -> str | None:
    """Return a deep link to the read-only transcript, if configured."""

    return build_manual_verification_dashboard_url(
        dashboard_public_url=dashboard_public_url,
        discord_guild_id=discord_guild_id,
        attempt_id=attempt_id,
        lang="en",
    )


async def _apply_review_roles(
    *,
    bot_client: DiscordBotClient,
    discord_guild_id: str,
    discord_user_id: str,
    approved: bool,
    unverified_role_id: str,
    member_role_id: str,
) -> None:
    """Apply the Unverified/Base Member role transition for a manual review.

    Mirrors automatic verification: approve grants the Base Member role and
    removes the Unverified role; reject re-applies the Unverified role. There is
    no separate "verified" role.
    """

    try:
        if approved:
            if member_role_id:
                await bot_client.add_member_role(
                    guild_id=discord_guild_id,
                    user_id=discord_user_id,
                    role_id=member_role_id,
                    reason="Norgoth manual review approved",
                )
            if unverified_role_id:
                await bot_client.remove_member_role(
                    guild_id=discord_guild_id,
                    user_id=discord_user_id,
                    role_id=unverified_role_id,
                    reason="Norgoth manual review approved",
                )
        elif unverified_role_id:
            await bot_client.add_member_role(
                guild_id=discord_guild_id,
                user_id=discord_user_id,
                role_id=unverified_role_id,
                reason="Norgoth manual review rejected",
            )
    except DiscordBotAPIError:
        logger.exception(
            "Manual-review role application failed for user %s in guild %s",
            discord_user_id,
            discord_guild_id,
        )


async def _send_manual_review_decision(
    *,
    bot_client: DiscordBotClient,
    discord_guild_id: str,
    legacy_log_channel_id: str,
    attempt_id: UUID,
    discord_user_id: str,
    reviewer_discord_id: str,
    approved: bool,
    transcript_url: str | None,
) -> None:
    """Post a structured Manual Review decision embed to the log channel.

    Exposes only moderation-relevant fields (never OAuth tokens or IPs) and
    disables all mentions so the notice cannot ping members.
    """

    log_channel_id, source = await resolve_verification_log_channel(
        discord_guild_id=discord_guild_id,
        event_type="verification_manual_decision",
        legacy_log_channel_id=legacy_log_channel_id,
    )
    if not log_channel_id:
        return

    decision = "Approved" if approved else "Denied"
    color = 0x34D399 if approved else 0xF87171

    fields = [
        {"name": "User", "value": f"<@{discord_user_id}> (`{discord_user_id}`)", "inline": False},
        {"name": "Decision", "value": decision, "inline": True},
        {
            "name": "Reviewer",
            "value": f"<@{reviewer_discord_id}>",
            "inline": True,
        },
    ]
    if transcript_url:
        fields.append(
            {
                "name": "Transcript",
                "value": f"[View review record]({transcript_url})",
                "inline": False,
            }
        )

    payload: dict[str, object] = {
        "embeds": [
            {
                "title": apply_log_title_emoji(
                    "verification_manual_decision",
                    "Manual Review Decision",
                ),
                "color": color,
                "fields": filter_log_embed_fields(fields),
            }
        ],
        "allowed_mentions": {"parse": []},
    }

    try:
        await bot_client.send_channel_message(log_channel_id, payload)
    except DiscordBotAPIError:
        logger.exception(
            "manual_review_decision_log_failed attempt_id=%s guild_id=%s "
            "channel_id=%s source=%s",
            attempt_id,
            discord_guild_id,
            log_channel_id,
            source,
        )
