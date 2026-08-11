"""Request and response schemas for Discord guilds."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DiscordSnowflakeValue = Annotated[
    str,
    Field(
        min_length=1,
        max_length=20,
        pattern=r"^[0-9]{1,20}$",
    ),
]


class GuildUpsertRequest(BaseModel):
    """Payload used to register or update a Discord guild."""

    discord_guild_name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
        ),
    ]
    discord_owner_id: DiscordSnowflakeValue


class GuildResponse(BaseModel):
    """Public representation of a registered Discord guild."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    discord_guild_id: DiscordSnowflakeValue
    discord_guild_name: str
    discord_owner_id: DiscordSnowflakeValue
    created_at: datetime
    updated_at: datetime
