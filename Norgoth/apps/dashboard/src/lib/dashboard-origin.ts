/**
 * Resolve the public dashboard origin for server-side absolute redirects.
 *
 * Prefer configured public URLs over `request.url`: behind Docker/Nginx the
 * standalone Next server often sees an internal bind origin such as
 * `http://0.0.0.0:3000`, which must never be returned to browsers.
 */

const LOCAL_FALLBACK_ORIGIN = "http://127.0.0.1:3000";

function parseHttpOrigin(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const trimmed = raw.trim();
  if (!trimmed) return null;

  try {
    const url = new URL(trimmed);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }
    if (url.hostname === "0.0.0.0") {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}

/**
 * Trusted public dashboard origin for redirects.
 *
 * Precedence matches the API (`dashboard_public_url`):
 * 1. `NORGOTH_DASHBOARD_URL`
 * 2. `NEXT_PUBLIC_DASHBOARD_URL`
 * 3. Safe origin from `fallbackRequestUrl` (not `0.0.0.0`)
 * 4. `http://127.0.0.1:3000`
 */
export function getDashboardOrigin(fallbackRequestUrl?: string): string {
  const configured =
    parseHttpOrigin(process.env.NORGOTH_DASHBOARD_URL) ||
    parseHttpOrigin(process.env.NEXT_PUBLIC_DASHBOARD_URL);

  if (configured) {
    return configured;
  }

  const fromRequest = parseHttpOrigin(fallbackRequestUrl);
  if (fromRequest) {
    return fromRequest;
  }

  return LOCAL_FALLBACK_ORIGIN;
}

/** Build an absolute dashboard URL using the trusted public origin. */
export function dashboardUrl(path: string, fallbackRequestUrl?: string): URL {
  const origin = getDashboardOrigin(fallbackRequestUrl);
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return new URL(normalized, origin);
}
