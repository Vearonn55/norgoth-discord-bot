"""Business operations for Discord verification attempts."""

from uuid import UUID

from app.models.enums import VerificationStatus
from app.models.verification_attempt import VerificationAttempt
from app.repositories.verification_log_repository import (
    VerificationLogRepository,
)
from app.security.ip_protection import IPProtectionService
from app.services.views import VerificationAttemptView


def _to_view(
    attempt: VerificationAttempt,
    *,
    discord_user_id: str,
) -> VerificationAttemptView:
    """Assemble a flat verification-attempt view from an ORM row."""

    return VerificationAttemptView(
        id=attempt.id,
        guild_id=attempt.guild_id,
        discord_user_id=discord_user_id,
        status=attempt.status,
        reason=attempt.reason,
        vpn_or_proxy_detected=attempt.vpn_or_proxy_detected,
        shared_ip_detected=attempt.shared_ip_detected,
        high_risk_guild_detected=attempt.high_risk_guild_detected,
        matched_high_risk_guild_ids=tuple(
            attempt.matched_high_risk_guild_ids or ()
        ),
        banned_ip_match_detected=attempt.banned_ip_match_detected,
        matched_banned_user_ids=tuple(attempt.matched_banned_user_ids or ()),
        review_evidence=attempt.review_evidence,
        reviewed_by=attempt.reviewed_by,
        reviewed_at=attempt.reviewed_at,
        created_at=attempt.created_at,
    )


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
        high_risk_guild_detected: bool = False,
        matched_high_risk_guild_ids: list[str] | None = None,
        banned_ip_match_detected: bool = False,
        matched_banned_user_ids: list[str] | None = None,
        review_evidence: dict | None = None,
    ) -> VerificationAttemptView:
        """Create a verification attempt with protected IP data."""

        ip_hash = self._ip_protection_service.hash_ip(ip_address)
        ip_encrypted = self._ip_protection_service.encrypt_ip(ip_address)

        attempt = await self._verification_log_repository.create(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
            status=status,
            reason=reason,
            ip_hash=ip_hash,
            ip_encrypted=ip_encrypted,
            vpn_or_proxy_detected=vpn_or_proxy_detected,
            shared_ip_detected=shared_ip_detected,
            high_risk_guild_detected=high_risk_guild_detected,
            matched_high_risk_guild_ids=matched_high_risk_guild_ids,
            banned_ip_match_detected=banned_ip_match_detected,
            matched_banned_user_ids=matched_banned_user_ids,
            review_evidence=review_evidence,
        )

        return _to_view(attempt, discord_user_id=discord_user_id)

    async def list_recent(
        self,
        *,
        guild_id: UUID,
        limit: int = 100,
        status: VerificationStatus | None = None,
    ) -> list[VerificationAttemptView]:
        """Return recent verification attempts for a guild."""

        attempts = await self._verification_log_repository.list_recent_by_guild(
            guild_id=guild_id,
            limit=limit,
            status=status,
        )

        return [
            _to_view(attempt, discord_user_id=attempt.user.discord_user_id)
            for attempt in attempts
        ]

    async def list_page(
        self,
        *,
        guild_id: UUID,
        limit: int,
        offset: int,
        status: VerificationStatus | None = None,
        query: str | None = None,
    ) -> tuple[list[VerificationAttemptView], int]:
        """Return a page of attempts plus the total matching the filters."""

        attempts = await self._verification_log_repository.list_page_by_guild(
            guild_id=guild_id,
            limit=limit,
            offset=offset,
            status=status,
            query=query,
        )
        total = await self._verification_log_repository.count_by_guild(
            guild_id=guild_id,
            status=status,
            query=query,
        )

        views = [
            _to_view(attempt, discord_user_id=attempt.user.discord_user_id)
            for attempt in attempts
        ]

        return views, total

    async def get_attempt(
        self,
        *,
        guild_id: UUID,
        attempt_id: UUID,
    ) -> VerificationAttemptView | None:
        """Return a single verification attempt for a guild."""

        attempt = await self._verification_log_repository.get_by_id(
            guild_id=guild_id,
            attempt_id=attempt_id,
        )

        if attempt is None:
            return None

        return _to_view(attempt, discord_user_id=attempt.user.discord_user_id)

    async def resolve_manual_review(
        self,
        *,
        guild_id: UUID,
        attempt_id: UUID,
        approved: bool,
        reviewer_discord_id: str,
    ) -> VerificationAttemptView | None:
        """Atomically apply an admin decision to a manual-review attempt.

        Uses a conditional update so only the first reviewer to act wins; a
        second concurrent decision gets ``None`` (the caller maps that to 409).
        Returns ``None`` when the attempt does not exist or was already
        resolved.
        """

        attempt = await self._verification_log_repository.claim_manual_review(
            guild_id=guild_id,
            attempt_id=attempt_id,
            approved=approved,
            reviewer_discord_id=reviewer_discord_id,
        )

        if attempt is None:
            return None

        return _to_view(attempt, discord_user_id=attempt.user.discord_user_id)

    async def get_open_manual_review_for_user(
        self,
        *,
        guild_id: UUID,
        discord_user_id: str,
    ) -> VerificationAttemptView | None:
        """Return the newest unresolved manual-review attempt for one user."""

        attempt = await self._verification_log_repository.get_open_manual_review_for_user(
            guild_id=guild_id,
            discord_user_id=discord_user_id,
        )
        if attempt is None:
            return None
        return _to_view(attempt, discord_user_id=attempt.user.discord_user_id)

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
