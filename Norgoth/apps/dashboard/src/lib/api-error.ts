/**
 * Parse NorBot API error envelopes: `{ error: { code, message, request_id } }`.
 */

export type ApiErrorBody = {
  code: string;
  message: string;
  requestId: string | null;
};

export async function readApiError(response: Response): Promise<ApiErrorBody> {
  try {
    const data = (await response.json()) as {
      error?: { code?: unknown; message?: unknown; request_id?: unknown };
      detail?: unknown;
    };
    if (data?.error && typeof data.error === "object") {
      const code =
        typeof data.error.code === "string" && data.error.code
          ? data.error.code
          : "http_error";
      const message =
        typeof data.error.message === "string" && data.error.message
          ? data.error.message
          : `Request failed (${response.status}).`;
      const requestId =
        typeof data.error.request_id === "string" ? data.error.request_id : null;
      return { code, message, requestId };
    }
    if (typeof data?.detail === "string" && data.detail) {
      return {
        code: "http_error",
        message: data.detail,
        requestId: null,
      };
    }
  } catch {
    /* ignore malformed / empty bodies */
  }
  return {
    code: "http_error",
    message: `Request failed (${response.status}).`,
    requestId: null,
  };
}

const RECONNECT_CODES = new Set([
  "discord_token_invalid",
  "discord_token_missing",
  "discord_scope_missing",
  "authentication_required",
]);

const RETRY_CODES = new Set([
  "discord_rate_limited",
  "discord_unavailable",
  "internal_server_error",
  "http_error",
]);

export function isReconnectErrorCode(code: string): boolean {
  return RECONNECT_CODES.has(code);
}

export function isRetryErrorCode(code: string): boolean {
  return RETRY_CODES.has(code);
}
