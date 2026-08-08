"""Database operations for Discord verification logs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_log import VerificationLog


class VerificationLogRepository:
    """Provide persistence operations for verification logs."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def add(
        self,
        verification_log: VerificationLog,
    ) -> VerificationLog:
        """Add a verification log and flush it to the database."""

        self._session.add(verification_log)
        await self._session.flush()

        return verification_log

    async def list_recent_by_guild(
        self,
        *,
        guild_id: UUID,
        limit: int = 100,
    ) -> list[VerificationLog]:
        """Return the most recent verification logs for a guild."""

        statement = (
            select(VerificationLog)
            .where(VerificationLog.guild_id == guild_id)
            .order_by(VerificationLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def list_user_ids_by_ip_hash(
        self,
        *,
        guild_id: UUID,
        ip_hash: str,
    ) -> list[str]:
        """Return Discord users that previously used the same IP hash."""

        statement = (
            select(VerificationLog.discord_user_id)
            .where(
                VerificationLog.guild_id == guild_id,
                VerificationLog.ip_hash == ip_hash,
            )
            .distinct()
        )
        result = await self._session.execute(statement)

        return list(result.scalars().all())
