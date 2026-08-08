"""Enumerations used by Discord verification persistence models."""

from enum import StrEnum


class VerificationStatus(StrEnum):
    """Final result of a verification attempt."""

    SUCCESS = "success"
    FAILED = "failed"


class UserListType(StrEnum):
    """Supported manual user-list entries."""

    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"
