"""Version 1 API endpoints for Discord guilds."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.api.v1.dependencies import (
    DatabaseSession,
    GuildServiceDependency,
)
from app.api.v1.dependencies_auth import guild_manager_dependency
from app.security.internal_auth import require_internal_token
from app.schemas.guild import GuildResponse, GuildUpsertRequest

router = APIRouter(
    prefix="/guilds",
    tags=["guilds"],
)

DiscordGuildIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]


@router.get(
    "/{discord_guild_id}",
    response_model=GuildResponse,
    dependencies=[Depends(guild_manager_dependency("discord_guild_id"))],
)
async def get_guild(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
) -> GuildResponse:
    """Return a registered Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    return GuildResponse.model_validate(guild)


@router.put(
    "/{discord_guild_id}",
    response_model=GuildResponse,
    dependencies=[Depends(require_internal_token)],
)
async def register_or_update_guild(
    discord_guild_id: DiscordGuildIdPath,
    payload: GuildUpsertRequest,
    guild_service: GuildServiceDependency,
    session: DatabaseSession,
) -> GuildResponse:
    """Register a Discord guild or update its Discord metadata."""

    guild = await guild_service.register_or_update(
        discord_guild_id=discord_guild_id,
        discord_guild_name=payload.discord_guild_name,
        discord_owner_id=payload.discord_owner_id,
    )

    # ``register_or_update`` returns a detached ``GuildView`` whose server-side
    # defaults were populated via RETURNING on flush, so only the commit remains.
    await session.commit()

    return GuildResponse.model_validate(guild)


@router.delete(
    "/{discord_guild_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(guild_manager_dependency("discord_guild_id"))],
)
async def remove_guild(
    discord_guild_id: DiscordGuildIdPath,
    guild_service: GuildServiceDependency,
    session: DatabaseSession,
) -> Response:
    """Remove a Discord guild and its owned records."""

    removed = await guild_service.remove(discord_guild_id)

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
