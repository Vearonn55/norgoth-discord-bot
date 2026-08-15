"""Norgoth unified API: campaigns, bot state, automation, and verification."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


from app.api.v1.router import api_router  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.exceptions import register_exception_handlers  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.middleware.csrf_origin import CsrfOriginMiddleware  # noqa: E402
from app.middleware.rate_limit import RateLimitMiddleware  # noqa: E402
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402
from app.middleware.request_size import RequestSizeLimitMiddleware  # noqa: E402
from app.middleware.uploads_auth import UploadsAuthMiddleware  # noqa: E402
from app.security.cors_origins import cors_allow_origins  # noqa: E402
from app.routes.activity import router as activity_router  # noqa: E402
from app.routes.analytics import router as analytics_router  # noqa: E402
from app.routes.automation import router as automation_router  # noqa: E402
from app.routes.automod import router as automod_router  # noqa: E402
from app.routes.autoresponder import router as autoresponder_router  # noqa: E402
from app.routes.bot import router as bot_router  # noqa: E402
from app.routes.campaigns import router as campaigns_router  # noqa: E402
from app.routes.campaigns import public_router as campaigns_public_router  # noqa: E402
from app.routes.campaigns import internal_router as campaigns_internal_router  # noqa: E402
from app.routes.honeypot import router as honeypot_router  # noqa: E402
from app.routes.rich_link_embeds import router as rich_link_embeds_router  # noqa: E402
from app.routes.rss_feeds import router as rss_feeds_router  # noqa: E402
from app.routes.ingest import router as ingest_router  # noqa: E402
from app.routes.internal_config import router as internal_config_router  # noqa: E402
from app.routes.moderation import router as moderation_router  # noqa: E402
from app.routes.notifications import router as notifications_router  # noqa: E402
from app.routes.content_notifications import router as content_notifications_router  # noqa: E402
from app.routes.content_notifications import catalog_router as content_notifications_catalog_router  # noqa: E402
from app.routes.embed_messages import router as embed_messages_router  # noqa: E402
from app.routes.embed_messages import internal_router as embed_messages_internal_router  # noqa: E402
from app.routes.logging_config import router as logging_config_router  # noqa: E402
from app.routes.platform_webhooks import router as platform_webhooks_router  # noqa: E402
from app.routes.uploads import router as uploads_router  # noqa: E402
from app.services.uploads.image_store import resolve_upload_root  # noqa: E402
from app.routes.raid import router as raid_router  # noqa: E402
from app.routes.role_menus import router as role_menus_router  # noqa: E402
from app.routes.invites import router as invites_router  # noqa: E402
from app.routes.leveling import router as leveling_router  # noqa: E402
from app.routes.feed_channels import router as feed_channels_router  # noqa: E402
from app.routes.modules import router as modules_router  # noqa: E402
from app.routes.server_logs import router as server_logs_router  # noqa: E402
from app.routes.system_audit_logs import router as system_audit_logs_router  # noqa: E402
from app.routes.tickets import router as tickets_router  # noqa: E402
from app.routes.tickets import public_router as tickets_public_router  # noqa: E402
from app.routes.tickets import session_router as tickets_session_router  # noqa: E402
from app.routes.verification_panel import router as verification_panel_router  # noqa: E402
from app.routes.observability import router as observability_router  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = cast(Settings, application.state.settings)
    configure_logging(settings.log_level)

    if settings.environment == "production":
        if not settings.auth_enforced:
            raise RuntimeError(
                "NORGOTH_AUTH_ENFORCED must be true in production."
            )
        if settings.enable_docs:
            raise RuntimeError(
                "NORGOTH_ENABLE_DOCS must be false in production."
            )
        if (
            settings.oauth_token_encryption_key is None
            and settings.webhook_encryption_key is None
        ):
            logger.warning(
                "Neither NORGOTH_OAUTH_TOKEN_ENCRYPTION_KEY nor "
                "NORGOTH_WEBHOOK_ENCRYPTION_KEY is set; operator Discord "
                "tokens will not be encrypted until one is configured."
            )

    logger.info(
        "Norgoth API startup completed: version=%s environment=%s",
        settings.app_version,
        settings.environment,
    )

    yield

    logger.info("Norgoth API shutdown completed.")


def create_application(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    application = FastAPI(
        title="Norgoth API",
        version=resolved_settings.app_version,
        docs_url="/docs" if resolved_settings.enable_docs else None,
        redoc_url="/redoc" if resolved_settings.enable_docs else None,
        openapi_url="/openapi.json" if resolved_settings.enable_docs else None,
        lifespan=lifespan,
    )

    application.state.settings = resolved_settings

    register_exception_handlers(application)

    # Last added = first executed. Request context wraps the rest.
    application.add_middleware(UploadsAuthMiddleware, settings=resolved_settings)
    application.add_middleware(CsrfOriginMiddleware, settings=resolved_settings)
    application.add_middleware(RateLimitMiddleware)
    application.add_middleware(RequestSizeLimitMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins(resolved_settings),
        # Allow dashboard access from other devices on the LAN (dev/staging).
        allow_origin_regex=(
            None
            if resolved_settings.environment == "production"
            else (
                r"https?://("
                r"localhost|127\.0\.0\.1|"
                r"192\.168\.\d{1,3}\.\d{1,3}|"
                r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
                r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
                r")(:\d+)?"
            )
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Redis-backed product routes (campaigns, bot state, automation).
    application.include_router(campaigns_router)
    application.include_router(campaigns_public_router)
    application.include_router(campaigns_internal_router)
    application.include_router(analytics_router)
    application.include_router(bot_router)
    application.include_router(automation_router)
    application.include_router(moderation_router)
    application.include_router(modules_router)
    application.include_router(automod_router)
    application.include_router(server_logs_router)
    application.include_router(system_audit_logs_router)
    application.include_router(tickets_router)
    application.include_router(tickets_public_router)
    application.include_router(tickets_session_router)
    application.include_router(verification_panel_router)
    application.include_router(leveling_router)
    application.include_router(feed_channels_router)
    application.include_router(autoresponder_router)
    application.include_router(role_menus_router)
    application.include_router(invites_router)
    application.include_router(notifications_router)
    application.include_router(content_notifications_router)
    application.include_router(content_notifications_catalog_router)
    application.include_router(platform_webhooks_router)
    application.include_router(uploads_router)
    application.include_router(embed_messages_router)
    application.include_router(embed_messages_internal_router)
    application.include_router(logging_config_router)
    application.include_router(raid_router)
    application.include_router(honeypot_router)
    application.include_router(rich_link_embeds_router)
    application.include_router(rss_feeds_router)
    application.include_router(observability_router)
    application.include_router(ingest_router)
    application.include_router(internal_config_router)
    application.include_router(activity_router)

    # Serve locally-uploaded embed media (read-only).
    upload_root = resolve_upload_root(resolved_settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    application.mount(
        "/uploads",
        StaticFiles(directory=str(upload_root)),
        name="uploads",
    )

    # Postgres-backed verification domain.
    application.include_router(
        api_router,
        prefix=resolved_settings.api_v1_prefix,
    )

    @application.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "Norgoth API",
            "status": "running",
            "architecture": "redis-queue-worker + postgres-verification",
        }

    return application


app = create_application()
