"""Database operations for Discord verification attempts."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.discord_user import DiscordUser
from app.models.enums import VerificationStatus
from app.models.verification_attempt import VerificationAttempt


class VerificationLogRepository:
    """Provide persistence operations for verification attempts."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""

        self._session = session

    async def create(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
        status: VerificationStatus,
        reason: str | None,
        ip_hash: str,
        ip_encrypted: bytes,
        vpn_or_proxy_detected: bool,
        shared_ip_detected: bool,
        high_risk_guild_detected: bool = False,
        matched_high_risk_guild_ids: list[str] | None = None,
    ) -> VerificationAttempt:
        """Insert a verification attempt (upserting the user dimension)."""

        from app.services.users import upsert_discord_user

        user = await upsert_discord_user(self._session, discord_user_id)

        attempt = VerificationAttempt(
            guild_id=guild_id,
            user_id=user.id,
            status=status,
            reason=reason,
            ip_hash=ip_hash,
            ip_encrypted=ip_encrypted,
            vpn_or_proxy_detected=vpn_or_proxy_detected,
            shared_ip_detected=shared_ip_detected,
            high_risk_guild_detected=high_risk_guild_detected,
            matched_high_risk_guild_ids=matched_high_risk_guild_ids or None,
        )
        self._session.add(attempt)
        await self._session.flush()
        attempt.user = user

        return attempt

    async def get_by_id(
        self,
        *,
        guild_id: UUID,
        attempt_id: UUID,
    ) -> VerificationAttempt | None:
        """Return a single verification attempt scoped to its guild."""

        statement = (
            select(VerificationAttempt)
            .where(
                VerificationAttempt.id == attempt_id,
                VerificationAttempt.guild_id == guild_id,
            )
            .options(selectinload(VerificationAttempt.user))
        )
        result = await self._session.execute(statement)

        return result.scalar_one_or_none()

    async def list_recent_by_guild(
        self,
        *,
        guild_id: UUID,
        limit: int = 100,
        status: VerificationStatus | None = None,
    ) -> list[VerificationAttempt]:
        """Return the most recent verification attempts for a guild."""

        statement = (
            select(VerificationAttempt)
            .where(VerificationAttempt.guild_id == guild_id)
            .order_by(VerificationAttempt.created_at.desc())
            .limit(limit)
            .options(selectinload(VerificationAttempt.user))
        )

        if status is not None:
            statement = statement.where(VerificationAttempt.status == status)

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def get_open_manual_review_for_user(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> VerificationAttempt | None:
        """Return the newest unresolved manual-review attempt for one user."""

        statement = (
            select(VerificationAttempt)
            .join(DiscordUser, VerificationAttempt.user_id == DiscordUser.id)
            .where(
                VerificationAttempt.guild_id == guild_id,
                DiscordUser.discord_user_id == discord_user_id,
                VerificationAttempt.status == VerificationStatus.MANUAL_REVIEW,
                VerificationAttempt.reviewed_at.is_(None),
            )
            .order_by(VerificationAttempt.created_at.desc())
            .limit(1)
            .options(selectinload(VerificationAttempt.user))
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    def _apply_filters(
        self,
        statement,
        *,
        status: VerificationStatus | None,
        query: str | None,
    ):
        """Apply the shared status + free-text filters to a select/count."""

        if status is not None:
            statement = statement.where(VerificationAttempt.status == status)
            if status is VerificationStatus.MANUAL_REVIEW:
                statement = statement.where(
                    VerificationAttempt.reviewed_at.is_(None),
                )

        if query:
            like = f"%{query.strip()}%"
            statement = statement.where(
                DiscordUser.discord_user_id.ilike(like)
                | DiscordUser.username_cache.ilike(like)
            )

        return statement

    async def list_page_by_guild(
        self,
        *,
        guild_id: UUID,
        limit: int,
        offset: int,
        status: VerificationStatus | None = None,
        query: str | None = None,
    ) -> list[VerificationAttempt]:
        """Return a page of verification attempts with optional search."""

        statement = (
            select(VerificationAttempt)
            .join(DiscordUser, VerificationAttempt.user_id == DiscordUser.id)
            .where(VerificationAttempt.guild_id == guild_id)
        )
        statement = self._apply_filters(statement, status=status, query=query)
        statement = (
            statement.order_by(VerificationAttempt.created_at.desc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(VerificationAttempt.user))
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def count_by_guild(
        self,
        *,
        guild_id: UUID,
        status: VerificationStatus | None = None,
        query: str | None = None,
    ) -> int:
        """Return the total number of attempts matching the filters."""

        statement = (
            select(func.count(VerificationAttempt.id))
            .select_from(VerificationAttempt)
            .join(DiscordUser, VerificationAttempt.user_id == DiscordUser.id)
            .where(VerificationAttempt.guild_id == guild_id)
        )
        statement = self._apply_filters(statement, status=status, query=query)

        result = await self._session.execute(statement)

        return int(result.scalar_one())

    async def save(self) -> None:
        """Flush pending changes (e.g. review resolution) to the database."""

        await self._session.flush()

    async def claim_manual_review(
        self,
        *,
        guild_id: UUID,
        attempt_id: UUID,
        approved: bool,
        reviewer_discord_id: str,
    ) -> VerificationAttempt | None:
        """Atomically resolve an attempt only if it is still awaiting review.

        Uses a single conditional ``UPDATE ... WHERE status = 'manual_review'``
        so two concurrent reviewers cannot both apply a decision. Returns the
        updated row when this call won the claim, or ``None`` when the attempt
        was already resolved (or does not exist).
        """

        new_status = (
            VerificationStatus.SUCCESS if approved else VerificationStatus.FAILED
        )
        statement = (
            update(VerificationAttempt)
            .where(
                VerificationAttempt.id == attempt_id,
                VerificationAttempt.guild_id == guild_id,
                VerificationAttempt.status == VerificationStatus.MANUAL_REVIEW,
            )
            .values(
                status=new_status,
                reviewed_by=reviewer_discord_id,
                reviewed_at=datetime.now(timezone.utc),
            )
            .returning(VerificationAttempt.id)
        )
        result = await self._session.execute(statement)

        if result.scalar_one_or_none() is None:
            return None

        return await self.get_by_id(guild_id=guild_id, attempt_id=attempt_id)

    async def list_user_ids_by_ip_hash(
        self,
        *,
        guild_id: UUID,
        ip_hash: str,
    ) -> list[str]:
        """Return Discord snowflakes that previously used the same IP hash."""

        statement = (
            select(DiscordUser.discord_user_id)
            .join(VerificationAttempt, VerificationAttempt.user_id == DiscordUser.id)
            .where(
                VerificationAttempt.guild_id == guild_id,
                VerificationAttempt.ip_hash == ip_hash,
            )
            .distinct()
        )
        result = await self._session.execute(statement)

        return list(result.scalars().all())
