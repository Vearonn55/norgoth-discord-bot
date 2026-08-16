"""Alembic migration environment."""

import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app.db.url import require_database_url
from app.models import (
    AnalyticsDaily,
    AutomodConfig,
    AutoresponderConfig,
    Campaign,
    CampaignActivity,
    CampaignRecipientResult,
    CampaignUnsubscribe,
    ContentCreatorSource,
    ContentEventType,
    DiscordLoggingEventType,
    DiscordManagedWebhook,
    DiscordUser,
    EmbedMediaAsset,
    EmbedMessage,
    EmbedMessageDelivery,
    Guild,
    GuildChannelBinding,
    GuildContentSubscription,
    GuildModerationEntry,
    GuildRoleBinding,
    GuildSettings,
    HoneypotConfig,
    HoneypotTrigger,
    InviteCounter,
    InviteJoinEvent,
    LevelingConfig,
    LoggingChannel,
    LoggingConfiguration,
    LoggingEventMapping,
    MemberXp,
    ModerationLogEntry,
    ModuleConfig,
    NormalizedContentEventRow,
    NotificationDeliveryAttempt,
    NotificationJob,
    NotificationSenderStyle,
    NotificationTemplate,
    Platform,
    PlatformMonitorCursor,
    PlatformSubscription,
    RaidConfig,
    RaidIncident,
    RichLinkEmbedsConfig,
    RoleMenuConfig,
    RssFeedConfig,
    RssFeedItem,
    ServerEventLogEntry,
    SystemAuditLog,
    Ticket,
    TicketConfig,
    TicketPanelsConfig,
    TicketShareToken,
    TicketTranscript,
    VerificationAttempt,
    WelcomeConfig,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

REGISTERED_MODEL_TYPES = (
    DiscordUser,
    SystemAuditLog,
    Guild,
    GuildSettings,
    GuildRoleBinding,
    GuildChannelBinding,
    VerificationAttempt,
    GuildModerationEntry,
    Platform,
    ContentEventType,
    DiscordLoggingEventType,
    ModuleConfig,
    WelcomeConfig,
    AutomodConfig,
    RaidConfig,
    HoneypotConfig,
    LevelingConfig,
    AutoresponderConfig,
    RoleMenuConfig,
    RichLinkEmbedsConfig,
    RssFeedConfig,
    RssFeedItem,
    TicketConfig,
    TicketPanelsConfig,
    RaidIncident,
    HoneypotTrigger,
    ModerationLogEntry,
    ServerEventLogEntry,
    InviteCounter,
    InviteJoinEvent,
    MemberXp,
    AnalyticsDaily,
    Ticket,
    TicketTranscript,
    TicketShareToken,
    Campaign,
    CampaignRecipientResult,
    CampaignActivity,
    CampaignUnsubscribe,
    ContentCreatorSource,
    PlatformSubscription,
    PlatformMonitorCursor,
    NormalizedContentEventRow,
    NotificationTemplate,
    NotificationSenderStyle,
    GuildContentSubscription,
    DiscordManagedWebhook,
    NotificationJob,
    NotificationDeliveryAttempt,
    EmbedMediaAsset,
    EmbedMessage,
    EmbedMessageDelivery,
    LoggingConfiguration,
    LoggingChannel,
    LoggingEventMapping,
)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the configured migration database URL."""

    settings = get_settings()

    return require_database_url(settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations without establishing a database connection."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    """Run migrations using an established synchronous connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an asynchronous engine and execute migrations."""

    configuration_section = config.get_section(config.config_ini_section) or {}
    configuration_section["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(run_sync_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations through an asynchronous database connection."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
