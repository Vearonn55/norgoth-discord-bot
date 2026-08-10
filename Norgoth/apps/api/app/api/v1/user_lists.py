"""Version 1 API endpoints for user whitelist and blacklist entries."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.api.v1.dependencies import (
    DatabaseSession,
    GuildServiceDependency,
    UserListServiceDependency,
)
from app.api.v1.dependencies_auth import (
    OperatorSessionDependency,
    guild_manager_dependency,
)
from app.models.enums import UserListType
from app.schemas.security import (
    UserListEntryResponse,
    UserListUpsertRequest,
)
from app.services.audit import record_audit

router = APIRouter(
    prefix="/guilds/{discord_guild_id}/user-list",
    tags=["user-list"],
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

UserListTypeQuery = Annotated[
    UserListType | None,
    Query(),
]


@router.get(
    "",
    response_model=list[UserListEntryResponse],
)
async def list_user_entries(
    discord_guild_id: DiscordSnowflakePath,
    guild_service: GuildServiceDependency,
    user_list_service: UserListServiceDependency,
    list_type: UserListTypeQuery = None,
) -> list[UserListEntryResponse]:
    """Return whitelist or blacklist entries for a Discord guild."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    entries = await user_list_service.list_entries(
        guild_id=guild.id,
        list_type=list_type,
    )

    return [UserListEntryResponse.model_validate(entry) for entry in entries]


@router.put(
    "/{discord_user_id}",
    response_model=UserListEntryResponse,
)
async def set_user_entry(
    discord_guild_id: DiscordSnowflakePath,
    discord_user_id: DiscordSnowflakePath,
    payload: UserListUpsertRequest,
    guild_service: GuildServiceDependency,
    user_list_service: UserListServiceDependency,
    session: DatabaseSession,
    operator: OperatorSessionDependency,
) -> UserListEntryResponse:
    """Create or update a user's whitelist or blacklist entry."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    entry = await user_list_service.set_entry(
        guild_id=guild.id,
        discord_user_id=discord_user_id,
        list_type=payload.list_type,
        reason=payload.reason,
    )

    await record_audit(
        session,
        entity_type=f"user_list_{payload.list_type.value}",
        action="upsert",
        guild_id=discord_guild_id,
        entity_id=discord_user_id,
        changes={
            "actor_discord_id": operator.user_id,
            "list_type": payload.list_type.value,
            "reason": payload.reason,
        },
    )

    await session.commit()

    return UserListEntryResponse.model_validate(entry)


@router.delete(
    "/{discord_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_user_entry(
    discord_guild_id: DiscordSnowflakePath,
    discord_user_id: DiscordSnowflakePath,
    guild_service: GuildServiceDependency,
    user_list_service: UserListServiceDependency,
    session: DatabaseSession,
    operator: OperatorSessionDependency,
) -> Response:
    """Remove a user's whitelist or blacklist entry."""

    guild = await guild_service.get_by_discord_guild_id(discord_guild_id)

    if guild is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discord guild not found.",
        )

    removed = await user_list_service.remove_entry(
        guild_id=guild.id,
        discord_user_id=discord_user_id,
    )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User list entry not found.",
        )

    await record_audit(
        session,
        entity_type="user_list",
        action="delete",
        guild_id=discord_guild_id,
        entity_id=discord_user_id,
        changes={"actor_discord_id": operator.user_id},
    )

    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
