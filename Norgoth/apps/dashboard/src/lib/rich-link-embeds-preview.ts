import { FIXED_REWRITE_HOSTS, type RichLinkEmbedsConfig, type RichLinkPlatforms } from "@/stores/rich-link-embeds-store";

function normalizeHost(host: string): string {
  let h = host.toLowerCase();
  if (h.startsWith("www.")) h = h.slice(4);
  return h;
}

const TIKTOK_SHORT_HOSTS = new Set(["vm.tiktok.com", "vt.tiktok.com"]);

export function previewRewrite(
  url: string,
  config: RichLinkEmbedsConfig,
): string | null {
  try {
    const parsed = new URL(url.trim());
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    if (parsed.username || parsed.password) {
      return null;
    }
    const host = normalizeHost(parsed.hostname);
    const path = parsed.pathname || "";
    const lower = path.toLowerCase();

    type Rule = {
      key: keyof RichLinkPlatforms;
      hosts: string[];
      match: () => boolean;
      rewrite: () => string;
    };

    const rules: Rule[] = [
      {
        key: "twitter",
        hosts: ["twitter.com", "x.com", "mobile.twitter.com", "mobile.x.com"],
        match: () => lower.includes("/status/"),
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.twitter}${path}`,
      },
      {
        key: "tiktok",
        hosts: ["tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"],
        match: () => {
          if (
            lower.includes("/video/") ||
            lower.includes("/photo/") ||
            lower.includes("/t/")
          ) {
            return true;
          }
          if (TIKTOK_SHORT_HOSTS.has(host)) {
            return /^\/[^/@]+\/?$/.test(path);
          }
          return false;
        },
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.tiktok}${path}`,
      },
      {
        key: "instagram",
        hosts: ["instagram.com"],
        match: () =>
          ["/p/", "/reel/", "/reels/", "/stories/"].some((t) =>
            lower.includes(t),
          ),
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.instagram}${path}`,
      },
      {
        key: "reddit",
        hosts: ["reddit.com", "old.reddit.com", "redd.it"],
        match: () => {
          if (lower.includes("/s/")) return false;
          return (
            lower.includes("/comments/") ||
            /^\/[a-z0-9]+\/?$/i.test(path) ||
            lower.includes("/r/") ||
            lower.includes("/user/") ||
            lower.includes("/u/")
          );
        },
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.reddit}${path}`,
      },
      {
        key: "pixiv",
        hosts: ["pixiv.net"],
        match: () =>
          lower.includes("/artworks/") ||
          lower.includes("/artwork/") ||
          (lower.includes("member_illust.php") &&
            parsed.searchParams.has("illust_id")),
        rewrite: () => {
          if (lower.includes("member_illust.php")) {
            const id = parsed.searchParams.get("illust_id");
            return id
              ? `https://${FIXED_REWRITE_HOSTS.pixiv}/artworks/${id}`
              : "";
          }
          return `https://${FIXED_REWRITE_HOSTS.pixiv}${path}`;
        },
      },
      {
        key: "youtube_shorts",
        hosts: ["youtube.com", "m.youtube.com"],
        match: () => /^\/shorts\/[A-Za-z0-9_-]{6,}/.test(path),
        rewrite: () => {
          const m = path.match(/^\/shorts\/([A-Za-z0-9_-]{6,})/);
          return m
            ? `https://${FIXED_REWRITE_HOSTS.youtube_shorts}/${m[1]}`
            : "";
        },
      },
    ];

    for (const rule of rules) {
      if (!config.platforms[rule.key]) continue;
      if (!rule.hosts.includes(host)) continue;
      if (!rule.match()) continue;
      const out = rule.rewrite();
      return out || null;
    }
    return null;
  } catch {
    return null;
  }
}
