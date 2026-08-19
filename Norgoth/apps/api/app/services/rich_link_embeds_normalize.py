"""Idempotent Link Embeds JSONB helpers (TikTok host remap, drop Bluesky)."""

from __future__ import annotations

from typing import Any

TIKTOK_REWRITE_HOST = "tnktok.com"
_LEGACY_TIKTOK_HOSTS = frozenset({"vxtiktok.com", "www.vxtiktok.com"})

DEFAULT_REWRITE_HOSTS: dict[str, str] = {
    "twitter": "fxtwitter.com",
    "tiktok": TIKTOK_REWRITE_HOST,
    "instagram": "instagram7.com",
    "reddit": "vxreddit.com",
    "pixiv": "phixiv.net",
    "youtube_shorts": "youtu.be",
}


def _tiktok_host_needs_remap(host: object) -> bool:
    value = str(host or "").strip().lower()
    return not value or value in _LEGACY_TIKTOK_HOSTS


def stored_needs_link_embeds_normalize(payload: dict[str, Any] | None) -> bool:
    """Return True when persisted JSON still has vxTikTok and/or Bluesky keys."""

    if not isinstance(payload, dict) or not payload:
        return False
    platforms = payload.get("platforms")
    hosts = payload.get("rewrite_hosts")
    if isinstance(platforms, dict) and "bluesky" in platforms:
        return True
    if isinstance(hosts, dict):
        if "bluesky" in hosts:
            return True
        if "tiktok" not in hosts or _tiktok_host_needs_remap(hosts.get("tiktok")):
            return True
        tiktok = str(hosts.get("tiktok") or "").strip().lower()
        if tiktok != TIKTOK_REWRITE_HOST:
            return True
    return False


def normalize_rich_link_embeds_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Remap TikTok host, drop Bluesky keys, force the operator host allowlist.

    Leaves ``platforms.tiktok`` and other platform booleans unchanged.
    """

    out = dict(payload) if isinstance(payload, dict) else {}
    platforms = dict(out.get("platforms") or {}) if isinstance(out.get("platforms"), dict) else {}
    platforms.pop("bluesky", None)
    out["platforms"] = platforms

    hosts = dict(out.get("rewrite_hosts") or {}) if isinstance(out.get("rewrite_hosts"), dict) else {}
    hosts.pop("bluesky", None)
    out["rewrite_hosts"] = dict(DEFAULT_REWRITE_HOSTS)
    return out


def disable_tiktok_for_downgrade(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Rollback helper: turn TikTok off; never restore vxTikTok."""

    out = normalize_rich_link_embeds_config(payload)
    platforms = dict(out.get("platforms") or {})
    platforms["tiktok"] = False
    out["platforms"] = platforms
    return out
