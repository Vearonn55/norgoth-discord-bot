/** Map RSS API / probe error codes to rssFeedsPage dictionary keys. */

export const RSS_ERROR_COPY_KEYS = {
  invalid_url: "probeInvalidUrl",
  unsafe_destination: "probeUnsafeDestination",
  not_found: "probeNotFound",
  access_denied: "probeAccessDenied",
  rate_limited: "probeRateLimited",
  remote_unavailable: "probeRemoteUnavailable",
  timeout: "probeTimeout",
  tls_failed: "probeTlsFailed",
  too_large: "probeTooLarge",
  unsupported_content: "probeUnsupportedContent",
  invalid_document: "probeInvalidDocument",
  rss_feed_limit_reached: "limitReached",
} as const;

export type RssErrorCopy = {
  probeFailed: string;
  probeInvalidUrl: string;
  probeUnsafeDestination: string;
  probeNotFound: string;
  probeAccessDenied: string;
  probeRateLimited: string;
  probeRemoteUnavailable: string;
  probeTimeout: string;
  probeTlsFailed: string;
  probeTooLarge: string;
  probeUnsupportedContent: string;
  probeInvalidDocument: string;
  limitReached: string;
};

export function rssErrorMessage(
  copy: RssErrorCopy,
  code: string | null | undefined,
  fallback?: string | null,
): string {
  if (code && code in RSS_ERROR_COPY_KEYS) {
    const key = RSS_ERROR_COPY_KEYS[code as keyof typeof RSS_ERROR_COPY_KEYS];
    return copy[key];
  }
  if (fallback && fallback.trim()) return fallback;
  return copy.probeFailed;
}
