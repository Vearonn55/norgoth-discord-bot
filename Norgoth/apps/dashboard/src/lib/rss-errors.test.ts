import { describe, expect, it } from "vitest";
import { rssErrorMessage } from "@/lib/rss-errors";

const copy = {
  probeFailed: "Probe failed.",
  probeInvalidUrl: "Invalid URL.",
  probeUnsafeDestination: "Unsafe destination.",
  probeNotFound: "Not found.",
  probeAccessDenied: "Access denied.",
  probeRateLimited: "Rate limited.",
  probeRemoteUnavailable: "Unavailable.",
  probeTimeout: "Timeout.",
  probeTlsFailed: "TLS failed.",
  probeTooLarge: "Too large.",
  probeUnsupportedContent: "Unsupported.",
  probeInvalidDocument: "Invalid document.",
  limitReached: "Limit reached.",
  duplicateFeed: "Duplicate feed.",
  persistFailed: "Persist failed.",
  saveSuccess: "Saved.",
  probeBeforeSaveHint: "Probe first.",
};

describe("rssErrorMessage", () => {
  it("maps structured probe codes", () => {
    expect(rssErrorMessage(copy, "invalid_url", "raw")).toBe("Invalid URL.");
    expect(rssErrorMessage(copy, "timeout", null)).toBe("Timeout.");
    expect(rssErrorMessage(copy, "rss_feed_limit_reached", "x")).toBe(
      "Limit reached.",
    );
    expect(rssErrorMessage(copy, "rss_feed_duplicate", "x")).toBe(
      "Duplicate feed.",
    );
    expect(rssErrorMessage(copy, "rss_feed_persist_failed", "x")).toBe(
      "Persist failed.",
    );
  });

  it("falls back to server message then probeFailed", () => {
    expect(rssErrorMessage(copy, "internal_server_error", "An unexpected server error occurred.")).toBe(
      "An unexpected server error occurred.",
    );
    expect(rssErrorMessage(copy, null, null)).toBe("Probe failed.");
  });
});
