"""Clean-room URL rewrite helpers for Link Embeds (NorBot-native).

Platform rules are independently designed. They are inspired by documented
public fixer-domain behavior, not copied from AGPL sources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse, urlunparse

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
# Prefer angle-bracket URLs and bare https URLs; strip trailing punctuation later.
_URL_RE = re.compile(
    r"(?:<(https?://[^>\s]+)>|(https?://[^\s<>()]+))",
    re.IGNORECASE,
)

# Operator allowlist — guild clients cannot choose other hosts.
ALLOWED_REWRITE_HOSTS: dict[str, str] = {
    "twitter": "fxtwitter.com",
    "bluesky": "bskx.app",
    "tiktok": "vxtiktok.com",
    "instagram": "ddinstagram.com",
    "reddit": "vxreddit.com",
    "pixiv": "phixiv.net",
    "youtube_shorts": "youtu.be",
}


@dataclass(frozen=True)
class PlatformRule:
    key: str
    # Exact hosts after lowercasing and stripping a single leading www.
    exact_hosts: tuple[str, ...]
    default_rewrite_host: str = ""


PLATFORM_RULES: tuple[PlatformRule, ...] = (
    PlatformRule(
        key="twitter",
        exact_hosts=("twitter.com", "x.com", "mobile.twitter.com", "mobile.x.com"),
        default_rewrite_host="fxtwitter.com",
    ),
    PlatformRule(
        key="bluesky",
        exact_hosts=("bsky.app",),
        default_rewrite_host="bskx.app",
    ),
    PlatformRule(
        key="tiktok",
        exact_hosts=("tiktok.com", "www.tiktok.com", "vm.tiktok.com"),
        default_rewrite_host="vxtiktok.com",
    ),
    PlatformRule(
        key="instagram",
        exact_hosts=("instagram.com", "www.instagram.com"),
        default_rewrite_host="ddinstagram.com",
    ),
    PlatformRule(
        key="reddit",
        exact_hosts=("reddit.com", "www.reddit.com", "old.reddit.com", "redd.it"),
        default_rewrite_host="vxreddit.com",
    ),
    PlatformRule(
        key="pixiv",
        exact_hosts=("pixiv.net", "www.pixiv.net"),
        default_rewrite_host="phixiv.net",
    ),
    PlatformRule(
        key="youtube_shorts",
        exact_hosts=("youtube.com", "www.youtube.com", "m.youtube.com"),
        default_rewrite_host="youtu.be",
    ),
)


def strip_code_regions(content: str) -> str:
    without_fences = _CODE_FENCE_RE.sub(" ", content)
    return _INLINE_CODE_RE.sub(" ", without_fences)


def extract_urls(content: str) -> list[str]:
    cleaned = strip_code_regions(content)
    urls: list[str] = []
    for match in _URL_RE.finditer(cleaned):
        raw = match.group(1) or match.group(2) or ""
        raw = raw.rstrip(".,);]>\"'")
        if raw:
            urls.append(raw)
    return urls


def _normalize_host(host: str) -> str:
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _host_allowed(host: str, exact_hosts: tuple[str, ...]) -> bool:
    normalized = _normalize_host(host)
    allowed = {_normalize_host(h) for h in exact_hosts}
    return normalized in allowed


def _path_ok(rule_key: str, path: str, query: str) -> bool:
    path = path or ""
    lower = path.lower()

    if rule_key == "twitter":
        return "/status/" in lower

    if rule_key == "bluesky":
        # /profile/{handle|did}/post/{tid}
        return "/profile/" in lower and "/post/" in lower

    if rule_key == "tiktok":
        return "/video/" in lower or "/t/" in lower

    if rule_key == "instagram":
        return (
            "/p/" in lower
            or "/reel/" in lower
            or "/reels/" in lower
            or "/stories/" in lower
        )

    if rule_key == "reddit":
        # Skip /s/ share shortcuts (may redirect off-site).
        if "/s/" in lower or re.search(r"^/s/", lower):
            return False
        return (
            "/comments/" in lower
            or re.search(r"^/[a-z0-9]+/?$", lower) is not None
            or "/r/" in lower
            or "/user/" in lower
            or "/u/" in lower
        )

    if rule_key == "pixiv":
        if "/artworks/" in lower or "/artwork/" in lower:
            return True
        if "member_illust.php" in lower:
            qs = parse_qs(query)
            return bool(qs.get("illust_id"))
        return False

    if rule_key == "youtube_shorts":
        return bool(re.match(r"^/shorts/[A-Za-z0-9_-]{6,}", path))

    return False


def _build_rewritten(
    *,
    rule_key: str,
    parsed,
    new_host: str,
) -> str | None:
    scheme = "https"
    path = parsed.path or ""
    query = ""

    if rule_key == "youtube_shorts":
        match = re.match(r"^/shorts/([A-Za-z0-9_-]{6,})", path)
        if not match:
            return None
        return f"https://youtu.be/{match.group(1)}"

    if rule_key == "pixiv" and "member_illust.php" in path.lower():
        qs = parse_qs(parsed.query)
        illust = (qs.get("illust_id") or [None])[0]
        if not illust:
            return None
        path = f"/artworks/{illust}"
        query = ""

    return urlunparse((scheme, new_host, path, "", query, ""))


def rewrite_url(
    url: str,
    *,
    enabled_platforms: dict[str, bool],
    rewrite_hosts: dict[str, str] | None = None,
) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    # Reject non-default ports to avoid weird lookalikes.
    if parsed.port not in (None, 80, 443):
        return None

    hosts = {**ALLOWED_REWRITE_HOSTS, **(rewrite_hosts or {})}

    for rule in PLATFORM_RULES:
        if not enabled_platforms.get(rule.key, False):
            continue
        if not _host_allowed(host, rule.exact_hosts):
            continue
        if not _path_ok(rule.key, parsed.path or "", parsed.query or ""):
            continue
        # Force allowlisted host; ignore unapproved client overrides.
        new_host = ALLOWED_REWRITE_HOSTS.get(rule.key) or rule.default_rewrite_host
        # Allow operator override only if still in allowlist values set.
        candidate = str(hosts.get(rule.key) or "").strip().lower()
        if candidate == ALLOWED_REWRITE_HOSTS.get(rule.key):
            new_host = candidate
        if not new_host:
            return None
        return _build_rewritten(rule_key=rule.key, parsed=parsed, new_host=new_host)
    return None


def transform_message_urls(
    content: str,
    *,
    enabled_platforms: dict[str, bool],
    rewrite_hosts: dict[str, str] | None = None,
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
