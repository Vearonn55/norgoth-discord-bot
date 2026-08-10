"""Per-guild feature configuration tables (Postgres source of truth).

Each config domain the bot reads from a Redis snapshot key is durably backed by
one row here. The API writes Postgres first, then rewrites the byte-compatible
Redis snapshot; Redis is a cache that is rehydrated from Postgres on a miss.

The canonical snapshot payload is stored verbatim in ``config`` (JSONB) so the
bot's read contract stays identical, with ``enabled`` mirrored to a scalar for
indexing/queries.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class _GuildConfigMixin(UUIDPrimaryKeyMixin, TimestampMixin):
    """Shared columns for a per-guild feature configuration row."""

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    config: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
        server_default=func.jsonb_build_object(),
    )


class ModuleConfig(_GuildConfigMixin, Base):
    """Per-guild module master switches snapshot (``:modules``)."""

    __tablename__ = "guild_module_configs"


class WelcomeConfig(_GuildConfigMixin, Base):
    """Welcome/leave/auto-role automation snapshot (``:automation``)."""

    __tablename__ = "welcome_configs"


class AutomodConfig(_GuildConfigMixin, Base):
    """Auto-moderation snapshot (``:automod``)."""

    __tablename__ = "automod_configs"


class RaidConfig(_GuildConfigMixin, Base):
    """Raid-protection config snapshot (``:raid``)."""

    __tablename__ = "raid_configs"


class HoneypotConfig(_GuildConfigMixin, Base):
    """Honeypot config snapshot (``:honeypot``)."""

    __tablename__ = "honeypot_configs"


class LevelingConfig(_GuildConfigMixin, Base):
    """Leveling config snapshot (``:leveling:config``)."""

    __tablename__ = "leveling_configs"


class AutoresponderConfig(_GuildConfigMixin, Base):
    """Autoresponder rules snapshot (``:autoresponses``)."""

    __tablename__ = "autoresponder_configs"


class RoleMenuConfig(_GuildConfigMixin, Base):
    """Self-assignable role menus snapshot (``:rolemenus``)."""

    __tablename__ = "role_menu_configs"


class TicketConfig(_GuildConfigMixin, Base):
    """Ticket system config snapshot (``:tickets:config``)."""

    __tablename__ = "ticket_configs"


class TicketPanelsConfig(_GuildConfigMixin, Base):
    """Ticket panel list snapshot (``:tickets:panels``)."""

    __tablename__ = "ticket_panels_configs"


class FeedConfig(_GuildConfigMixin, Base):
    """Feed Channels settings snapshot (``:feed:config``)."""

    __tablename__ = "feed_configs"
