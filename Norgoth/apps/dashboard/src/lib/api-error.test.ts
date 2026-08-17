import { describe, expect, it } from "vitest";
import {
  isReconnectErrorCode,
  isRetryErrorCode,
  readApiError,
} from "./api-error";

describe("readApiError", () => {
  it("parses structured error envelopes", async () => {
    const response = new Response(
      JSON.stringify({
        error: {
          code: "discord_token_invalid",
          message: "Reconnect Discord",
          request_id: "req-1",
        },
      }),
      { status: 401 },
    );
    await expect(readApiError(response)).resolves.toEqual({
      code: "discord_token_invalid",
      message: "Reconnect Discord",
      requestId: "req-1",
    });
  });

  it("parses FastAPI detail objects", async () => {
    const response = new Response(
      JSON.stringify({
        detail: {
          code: "automod_channel_rule_conflict",
          message: "A channel cannot be both Image Only and Link Only.",
        },
      }),
      { status: 409 },
    );
    await expect(readApiError(response)).resolves.toEqual({
      code: "automod_channel_rule_conflict",
      message: "A channel cannot be both Image Only and Link Only.",
      requestId: null,
    });
  });
    const response = new Response("", { status: 502 });
    await expect(readApiError(response)).resolves.toEqual({
      code: "http_error",
      message: "Request failed (502).",
      requestId: null,
    });
  });
});

describe("error code helpers", () => {
  it("classifies reconnect and retry codes", () => {
    expect(isReconnectErrorCode("discord_token_invalid")).toBe(true);
    expect(isReconnectErrorCode("discord_unavailable")).toBe(false);
    expect(isRetryErrorCode("discord_rate_limited")).toBe(true);
    expect(isRetryErrorCode("discord_scope_missing")).toBe(false);
  });
});
