"""Version 1 API endpoints for Discord verification logs."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.v1.dependencies import (
    GuildServiceDependency,
    VerificationLogServiceDependency,
)
from app.schemas.verification_log import (
    VerificationLogResponse,
)

router = APIRouter(
    prefix="/guilds/{discord_guild_id}/verification-logs",
    tags=["verification-logs"],
)

DiscordGuildIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]

VerificationLogLimitQuery = Annotated[
    int,
    Query(
        ge=1,
        le=100,
    ),
]


@router.get(
    "",
    response_model=list[VerificationLogResponse],
)
async def list_verification_logs(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
    verification_log_service: VerificationLogServiceDependency,
    limit: VerificationLogLimitQuery = 50,
) -> list[VerificationLogResponse]:
    """Return recent verification attempts for a Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    verification_logs = await verification_log_service.list_recent(
        guild_id=guild.id,
        limit=limit,
    )

    return [
        VerificationLogResponse.model_validate(verification_log)
        for verification_log in verification_logs
    ]
