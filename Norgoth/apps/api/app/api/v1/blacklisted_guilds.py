"""Version 1 API endpoints for blacklisted Discord guilds."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.api.v1.dependencies import (
    BlacklistedGuildServiceDependency,
    DatabaseSession,
    GuildServiceDependency,
)
from app.api.v1.dependencies_auth import guild_manager_dependency
from app.schemas.security import (
    BlacklistedGuildResponse,
    BlacklistedGuildUpsertRequest,
)

router = APIRouter(
    prefix="/guilds/{discord_guild_id}/blacklisted-guilds",
    tags=["blacklisted-guilds"],
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
    response_model=list[BlacklistedGuildResponse],
)
async def list_blacklisted_guilds(
    discord_guild_id: DiscordSnowflakePath,
    guild_service: GuildServiceDependency,
    blacklisted_guild_service: BlacklistedGuildServiceDependency,
) -> list[BlacklistedGuildResponse]:
    """Return blacklisted Discord guilds configured by one server."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    entries = await blacklisted_guild_service.list_entries(guild.id)

    return [BlacklistedGuildResponse.model_validate(entry) for entry in entries]


@router.put(
    "/{blacklisted_discord_guild_id}",
    response_model=BlacklistedGuildResponse,
)
async def set_blacklisted_guild(
    discord_guild_id: DiscordSnowflakePath,
    blacklisted_discord_guild_id: DiscordSnowflakePath,
    payload: BlacklistedGuildUpsertRequest,
    guild_service: GuildServiceDependency,
    blacklisted_guild_service: BlacklistedGuildServiceDependency,
    session: DatabaseSession,
) -> BlacklistedGuildResponse:
    """Create or update a blacklisted Discord guild entry."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    entry = await blacklisted_guild_service.set_entry(
        guild_id=guild.id,
        blacklisted_discord_guild_id=blacklisted_discord_guild_id,
        reason=payload.reason,
    )

    await session.commit()
    await session.refresh(entry)

    return BlacklistedGuildResponse.model_validate(entry)


@router.delete(
    "/{blacklisted_discord_guild_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_blacklisted_guild(
    discord_guild_id: DiscordSnowflakePath,
    blacklisted_discord_guild_id: DiscordSnowflakePath,
    guild_service: GuildServiceDependency,
    blacklisted_guild_service: BlacklistedGuildServiceDependency,
    session: DatabaseSession,
) -> Response:
    """Remove a blacklisted Discord guild entry."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    removed = await blacklisted_guild_service.remove_entry(
        guild_id=guild.id,
        blacklisted_discord_guild_id=blacklisted_discord_guild_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklisted guild entry not found.",
        )

    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
