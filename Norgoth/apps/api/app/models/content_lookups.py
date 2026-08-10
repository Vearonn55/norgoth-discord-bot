"""Reference dimensions for the content-notifications subsystem.

These lookup tables (from the enterprise DBML) enumerate the supported creator
platforms and the normalized content event types. The content pipeline stores
``platform`` / ``event_type`` as strings on the hot event/creator tables (to stay
byte-compatible with the worker and bot), and these tables provide the seeded,
validated dimension the dashboard and admin tooling reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class Platform(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A supported content platform (twitch, youtube, tiktok, kick, x)."""

    __tablename__ = "platforms"

    key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    event_types: Mapped[list[ContentEventType]] = relationship(
        back_populates="platform",
        cascade="all, delete-orphan",
    )


class ContentEventType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A normalized content event type (for example ``twitch.live``)."""

    __tablename__ = "content_event_types"
    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "key",
            name="uq_content_event_types_platform_key",
        ),
    )

    platform_id: Mapped[UUID] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    platform: Mapped[Platform] = relationship(back_populates="event_types")
