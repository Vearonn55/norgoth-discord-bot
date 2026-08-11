"""Enumerations used by Discord verification persistence models."""

from enum import StrEnum


class VerificationStatus(StrEnum):
    """Final result (or interim state) of a verification attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class UserListType(StrEnum):
    """Supported manual user-list entries."""

    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"


class RiskAction(StrEnum):
    """Configured outcome when a risk detector fires.

    ``DENY`` rejects verification outright; ``MANUAL_REVIEW`` routes the
    attempt into the manual-review queue instead of an automatic decision.
    """

    DENY = "deny"
    MANUAL_REVIEW = "manual_review"


class GuildRolePurpose(StrEnum):
    """Normalized role bindings a guild can configure.

    Verification converges on a two-role model: remove the ``UNVERIFIED`` role
    and grant the base ``MEMBER`` role on success. The legacy ``verified`` role
    was removed; see migration ``0011_drop_verified_role``.
    """

    UNVERIFIED = "unverified"
    MEMBER = "member"
    MANUAL_REVIEW = "manual_review"


class GuildChannelPurpose(StrEnum):
    """Normalized channel bindings a guild can configure."""

    VERIFICATION = "verification"
    LOG = "log"
