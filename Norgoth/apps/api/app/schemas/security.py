"""Request and response schemas for verification security lists."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import UserListType

DiscordSnowflakeValue = Annotated[
    str,
    Field(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]

OptionalReason = Annotated[
    str | None,
    Field(max_length=200),
]


class UserListUpsertRequest(BaseModel):
    """Payload used to create or update a user list entry."""

    list_type: UserListType
    reason: OptionalReason = None


class UserListEntryResponse(BaseModel):
    """Public representation of a whitelist or blacklist entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guild_id: UUID
    discord_user_id: DiscordSnowflakeValue
    list_type: UserListType
    reason: str | None
    created_at: datetime
    updated_at: datetime


class BlacklistedGuildUpsertRequest(BaseModel):
    """Payload used to create or update a blacklisted Discord guild."""

    reason: OptionalReason = None


class BlacklistedGuildResponse(BaseModel):
    """Public representation of a blacklisted Discord guild."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    guild_id: UUID
    blacklisted_discord_guild_id: DiscordSnowflakeValue
    reason: str | None
    created_at: datetime
    updated_at: datetime
