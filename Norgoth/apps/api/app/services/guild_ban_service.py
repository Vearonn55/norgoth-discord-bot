"""Business operations for guild-scoped active ban tracking."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.guild_active_ban import GuildActiveBan
from app.repositories.discord_guild_repository import DiscordGuildRepository
from app.repositories.guild_active_ban_repository import GuildActiveBanRepository
from app.security.ip_protection import IPProtectionService


class GuildBanService:
    """Manage active ban registry entries for verification correlation."""

    def __init__(
        self,
        *,
        guild_repository: DiscordGuildRepository,
        ban_repository: GuildActiveBanRepository,
        ip_protection_service: IPProtectionService | None = None,
    ) -> None:
        self._guild_repository = guild_repository
        self._ban_repository = ban_repository
        self._ip_protection_service = ip_protection_service

    async def _resolve_guild_id(self, discord_guild_id: str) -> UUID | None:
        guild = await self._guild_repository.get_by_discord_guild_id(discord_guild_id)
        return guild.id if guild is not None else None

    async def upsert_active_ban(
        self,
        *,
        discord_guild_id: str,
        discord_user_id: str,
        username_snapshot: str | None = None,
        display_name_snapshot: str | None = None,
        source: str = "gateway_ban",
        banned_at: datetime | None = None,
    ) -> GuildActiveBan | None:
        guild_id = await self._resolve_guild_id(discord_guild_id)
        if guild_id is None:
            return None
        return await self._ban_repository.upsert_active_ban(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            username_snapshot=username_snapshot,
            display_name_snapshot=display_name_snapshot,
            source=source,
            banned_at=banned_at,
        )

    async def deactivate_ban(
        self,
        *,
        discord_guild_id: str,
        discord_user_id: str,
        source: str = "gateway_unban",
        unbanned_at: datetime | None = None,
    ) -> GuildActiveBan | None:
        guild_id = await self._resolve_guild_id(discord_guild_id)
        if guild_id is None:
            return None
        return await self._ban_repository.deactivate_ban(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            source=source,
            unbanned_at=unbanned_at,
        )

    async def list_active_banned_user_ids(
        self,
        *,
        guild_id: UUID,
    ) -> list[str]:
        return await self._ban_repository.list_active_banned_user_ids(guild_id=guild_id)

    async def find_active_bans_by_ip_hash(
        self,
        *,
        guild_id: UUID,
        ip_hash: str,
        exclude_discord_user_id: str,
    ) -> list[str]:
        return await self._ban_repository.find_active_bans_by_ip_hash(
            guild_id=guild_id,
            ip_hash=ip_hash,
            exclude_discord_user_id=exclude_discord_user_id,
        )

    async def find_banned_users_with_ip(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        ip_address: str,
    ) -> list[str]:
        if self._ip_protection_service is None:
            return []
        ip_hash = self._ip_protection_service.hash_ip(ip_address)
        return await self._ban_repository.find_active_bans_by_ip_hash(
            guild_id=guild_id,
            ip_hash=ip_hash,
            exclude_discord_user_id=discord_user_id,
        )

    async def get_ban_snapshots(
        self,
        *,
        guild_id: UUID,
        discord_user_ids: list[str],
    ) -> dict[str, GuildActiveBan]:
        snapshots: dict[str, GuildActiveBan] = {}
        for user_id in discord_user_ids:
            row = await self._ban_repository.get_by_guild_and_user(
                guild_id=guild_id,
                discord_user_id=user_id,
            )
            if row is not None:
                snapshots[user_id] = row
        return snapshots

    async def reconcile_active_bans(
        self,
        *,
        discord_guild_id: str,
        banned_users: list[tuple[str, str | None, str | None]],
    ) -> int:
        """Idempotently upsert active bans from a Discord ban list snapshot."""

        guild_id = await self._resolve_guild_id(discord_guild_id)
        if guild_id is None:
            return 0
        synced = 0
        for discord_user_id, username, display_name in banned_users:
            await self._ban_repository.upsert_active_ban(
                guild_id=guild_id,
                discord_user_id=discord_user_id,
                username_snapshot=username,
                display_name_snapshot=display_name,
                source="reconcile",
            )
            synced += 1
        return synced
