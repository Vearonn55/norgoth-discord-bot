"""Discord Link button components for live stream notifications."""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.content_platforms.types import (
    ContentEventType,
    NormalizedContentEvent,
)
from app.services.content_notifications.i18n import watch_on_platform_label
from app.services.content_notifications.stream_urls import validate_canonical_stream_url
from app.services.content_notifications.tag_registry import PLATFORM_ICONS

logger = logging.getLogger("norgoth.content.components")


def build_stream_watch_components(
    event: NormalizedContentEvent,
    *,
    locale: str | None = "en",
) -> list[dict[str, Any]] | None:
    """Build a single action row with a platform Link button, or None."""

    if event.event_type != ContentEventType.STREAM_STARTED:
        return None

    raw_url = event.playable_url or event.content_url
    safe_url = validate_canonical_stream_url(
        event.platform,
        raw_url,
        video_id=event.external_content_id
        if event.platform.value == "youtube"
        else None,
    )
    if not safe_url:
        logger.info(
            "cn_link_button_omitted platform=%s event_type=%s reason=invalid_url",
            event.platform.value,
            event.event_type.value,
        )
        return None

    icon = PLATFORM_ICONS.get(event.platform, "▶️")
    label = watch_on_platform_label(event.platform, locale=locale)
    button_label = f"{icon} {label}"[:80]

    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": button_label,
                    "url": safe_url,
                }
            ],
        }
    ]
