"""Business operations for Discord verification logs."""

from uuid import UUID

from app.models.enums import VerificationStatus
from app.models.verification_log import VerificationLog
from app.repositories.verification_log_repository import (
    VerificationLogRepository,
)
from app.security.ip_protection import IPProtectionService


class VerificationLogService:
    """Manage verification history and shared-IP lookups."""

    def __init__(
        self,
        verification_log_repository: VerificationLogRepository,
        ip_protection_service: IPProtectionService,
    ) -> None:
        """Initialize the service with persistence and IP protection."""

        self._verification_log_repository = verification_log_repository
        self._ip_protection_service = ip_protection_service

    async def create_log(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        status: VerificationStatus,
        reason: str | None,
        ip_address: str,
        vpn_or_proxy_detected: bool,
        shared_ip_detected: bool,
        blacklisted_guild_detected: bool,
    ) -> VerificationLog:
        """Create a verification log with protected IP data."""

        ip_hash = self._ip_protection_service.hash_ip(ip_address)
        ip_encrypted = self._ip_protection_service.encrypt_ip(ip_address)

        verification_log = VerificationLog(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            status=status,
            reason=reason,
            ip_hash=ip_hash,
            ip_encrypted=ip_encrypted,
            vpn_or_proxy_detected=vpn_or_proxy_detected,
            shared_ip_detected=shared_ip_detected,
            blacklisted_guild_detected=(blacklisted_guild_detected),
        )

        return await self._verification_log_repository.add(verification_log)

    async def list_recent(
        self,
        *,
        guild_id: UUID,
        limit: int = 100,
    ) -> list[VerificationLog]:
        """Return recent verification logs for a guild."""

        return await self._verification_log_repository.list_recent_by_guild(
            guild_id=guild_id,
            limit=limit,
        )

    async def find_other_users_with_ip(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        ip_address: str,
    ) -> list[str]:
        """Return other Discord users that used the same IP."""

        ip_hash = self._ip_protection_service.hash_ip(ip_address)

        user_ids = await self._verification_log_repository.list_user_ids_by_ip_hash(
            guild_id=guild_id,
            ip_hash=ip_hash,
        )

        return [user_id for user_id in user_ids if user_id != discord_user_id]

    async def has_shared_ip(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        ip_address: str,
    ) -> bool:
        """Return whether another Discord user used the same IP."""

        other_user_ids = await self.find_other_users_with_ip(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            ip_address=ip_address,
        )

        return bool(other_user_ids)
