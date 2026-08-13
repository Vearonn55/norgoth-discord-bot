"""Clean-room URL rewrite helpers for Rich Link Embeds (NorBot-native).

Platform rules are intentionally simple and independently testable. They are
inspired by documented public fixer-domain behavior, not copied from AGPL
sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

# Strip fenced and inline code before URL extraction.
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


@dataclass(frozen=True)
class PlatformRule:
    key: str
    host_suffixes: tuple[str, ...]
    path_contains: tuple[str, ...] = ()
    default_rewrite_host: str = ""


PLATFORM_RULES: tuple[PlatformRule, ...] = (
    PlatformRule(
        key="twitter",
        host_suffixes=("twitter.com", "x.com"),
        path_contains=("/status/",),
        default_rewrite_host="fxtwitter.com",
    ),
    PlatformRule(
        key="bluesky",
        host_suffixes=("bsky.app",),
        path_contains=("/profile/", "/post/"),
        default_rewrite_host="bskx.app",
    ),
    PlatformRule(
        key="tiktok",
        host_suffixes=("tiktok.com",),
        path_contains=("/video/", "/t/"),
        default_rewrite_host="vxtiktok.com",
    ),
    PlatformRule(
        key="reddit",
        host_suffixes=("reddit.com", "redd.it"),
        path_contains=(),
        default_rewrite_host="vxreddit.com",
    ),
)


def strip_code_regions(content: str) -> str:
    without_fences = _CODE_FENCE_RE.sub(" ", content)
    return _INLINE_CODE_RE.sub(" ", without_fences)


def extract_urls(content: str) -> list[str]:
    cleaned = strip_code_regions(content)
    urls: list[str] = []
    for match in _URL_RE.finditer(cleaned):
        raw = match.group(0).rstrip(".,);]>\"'")
        urls.append(raw)
    return urls


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    host = host.lower().removeprefix("www.")
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def rewrite_url(
    url: str,
    *,
    enabled_platforms: dict[str, bool],
    rewrite_hosts: dict[str, str],
) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None

    for rule in PLATFORM_RULES:
        if not enabled_platforms.get(rule.key, False):
            continue
        if not _host_matches(host, rule.host_suffixes):
            continue
        path = parsed.path or ""
        if rule.path_contains and not any(token in path for token in rule.path_contains):
            # Reddit short links may lack /comments/ — still rewrite.
            if rule.key != "reddit":
                continue
        new_host = (rewrite_hosts.get(rule.key) or rule.default_rewrite_host).strip()
        if not new_host:
            return None
        # Drop query/fragment by default (tracking parameters).
        rewritten = urlunparse(
            (parsed.scheme, new_host, parsed.path, "", "", "")
        )
        return rewritten
    return None


def transform_message_urls(
    content: str,
    *,
    enabled_platforms: dict[str, bool],
    rewrite_hosts: dict[str, str],
    max_links: int = 3,
) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in extract_urls(content):
        rewritten = rewrite_url(
            url,
            enabled_platforms=enabled_platforms,
            rewrite_hosts=rewrite_hosts,
        )
        if not rewritten or rewritten in seen or rewritten == url:
            continue
        seen.add(rewritten)
        out.append(rewritten)
        if len(out) >= max_links:
            break
    return out
