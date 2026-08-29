"""Version 1 API endpoints for high-risk Discord guilds.

High-risk guilds drive the manual-review verification path: a verifying user
who belongs to any configured high-risk guild is routed to ``manual_review``
rather than auto-verified. Changes are audit-logged because they materially
affect verification outcomes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.api.v1.dependencies import (
    DatabaseSession,
    GuildServiceDependency,
    HighRiskGuildServiceDependency,
)
from app.api.v1.dependencies_auth import (
    OperatorSessionDependency,
    guild_manager_dependency,
)
from app.schemas.security import (
    HighRiskGuildResponse,
    HighRiskGuildUpsertRequest,
)
from app.services.audit import record_audit

router = APIRouter(
    prefix="/guilds/{discord_guild_id}/high-risk-guilds",
    tags=["high-risk-guilds"],
    dependencies=[Depends(guild_manager_dependency("discord_guild_id"))],
)

DiscordSnowflakePath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]


@router.get(
    "",
    response_model=list[HighRiskGuildResponse],
)
async def list_high_risk_guilds(
    discord_guild_id: DiscordSnowflakePath,
    guild_service: GuildServiceDependency,
    high_risk_guild_service: HighRiskGuildServiceDependency,
) -> list[HighRiskGuildResponse]:
    """Return high-risk Discord guilds configured by one server."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    entries = await high_risk_guild_service.list_entries(guild.id)

    return [HighRiskGuildResponse.model_validate(entry) for entry in entries]


@router.put(
    "/{high_risk_discord_guild_id}",
    response_model=HighRiskGuildResponse,
)
async def set_high_risk_guild(
    discord_guild_id: DiscordSnowflakePath,
    high_risk_discord_guild_id: DiscordSnowflakePath,
    payload: HighRiskGuildUpsertRequest,
    guild_service: GuildServiceDependency,
    high_risk_guild_service: HighRiskGuildServiceDependency,
    session: DatabaseSession,
    operator: OperatorSessionDependency,
) -> HighRiskGuildResponse:
    """Create or update a high-risk Discord guild entry."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    if high_risk_discord_guild_id == discord_guild_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "self_reference_server_id",
                "message": "A server cannot list itself as a High Risk Server.",
            },
        )

    entry = await high_risk_guild_service.set_entry(
        guild_id=guild.id,
        high_risk_discord_guild_id=high_risk_discord_guild_id,
        reason=payload.reason,
        created_by=operator.user_id,
    )

    await record_audit(
        session,
        entity_type="high_risk_guild",
        action="upsert",
        guild_id=discord_guild_id,
        entity_id=high_risk_discord_guild_id,
        changes={
            "actor_discord_id": operator.user_id,
            "reason": payload.reason,
        },
    )

    await session.commit()
    await session.refresh(entry)

    return HighRiskGuildResponse.model_validate(entry)


@router.delete(
    "/{high_risk_discord_guild_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_high_risk_guild(
    discord_guild_id: DiscordSnowflakePath,
    high_risk_discord_guild_id: DiscordSnowflakePath,
    guild_service: GuildServiceDependency,
    high_risk_guild_service: HighRiskGuildServiceDependency,
    session: DatabaseSession,
    operator: OperatorSessionDependency,
) -> Response:
    """Remove a high-risk Discord guild entry."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    removed = await high_risk_guild_service.remove_entry(
        guild_id=guild.id,
        high_risk_discord_guild_id=high_risk_discord_guild_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="High-risk guild entry not found.",
        )

    await record_audit(
        session,
        entity_type="high_risk_guild",
        action="delete",
        guild_id=discord_guild_id,
        entity_id=high_risk_discord_guild_id,
        changes={"actor_discord_id": operator.user_id},
    )

    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
