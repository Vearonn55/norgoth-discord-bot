import { readApiError } from "@/lib/api-error";

/**
 * Resolve the API base URL at call time.
 * - Browser: same-origin `/norgoth-api` proxy (LAN-safe; only port 3000 needed)
 * - Server/SSR: loopback API
 */
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return "/norgoth-api";
  }

  return (
    process.env.NORGOTH_API_INTERNAL_URL?.trim() || "http://127.0.0.1:8000"
  );
}

/** Build a full API URL for the current runtime (call at request time). */
export function apiUrl(path: string): string {
  const base = getApiBaseUrl().replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

/**
 * Same-origin proxy path for <a href> / SSR markup.
 * Always uses `/norgoth-api` so server and client HTML match (no hydration mismatch).
 */
export function browserApiUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `/norgoth-api${suffix}`;
}

/**
 * Extract a human-readable error message from a failed API response.
 * Understands `{ error: { code, message } }` and FastAPI `{ detail }`.
 */
export async function readError(response: Response): Promise<string> {
  const parsed = await readApiError(response);
  return parsed.message;
}
