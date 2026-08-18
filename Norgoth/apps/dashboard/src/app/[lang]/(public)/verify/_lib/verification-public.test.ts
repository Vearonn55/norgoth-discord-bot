import { describe, expect, it } from "vitest";
import {
  mapAuthorizeStateToVisualState,
  mapOutcomeToVisualState,
  startVerificationHref,
} from "./verification-public";

describe("verification public mappings", () => {
  it("maps callback outcomes to visual states", () => {
    expect(mapOutcomeToVisualState("granted")).toBe("success");
    expect(mapOutcomeToVisualState("pending")).toBe("manual_review");
    expect(mapOutcomeToVisualState("denied")).toBe("denied");
    expect(mapOutcomeToVisualState("error")).toBe("error");
  });

  it("maps authorize states to visual states", () => {
    expect(mapAuthorizeStateToVisualState("ready")).toBe("ready");
    expect(mapAuthorizeStateToVisualState("degraded")).toBe("unavailable");
    expect(mapAuthorizeStateToVisualState("not_configured")).toBe("unavailable");
  });

  it("builds start links through browser api proxy", () => {
    expect(startVerificationHref("123", "tr")).toBe(
      "/norgoth-api/api/v1/oauth/discord/authorize/123?lang=tr&start=1",
    );
  });
});
