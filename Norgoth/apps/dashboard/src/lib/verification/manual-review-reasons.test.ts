import { describe, expect, it } from "vitest";
import {
  deriveManualReviewReasons,
  manualReviewReasonLabel,
} from "./manual-review-reasons";

describe("deriveManualReviewReasons", () => {
  it("includes banned IP match and risk provider codes", () => {
    expect(
      deriveManualReviewReasons({
        banned_ip_match_detected: true,
        reason: "risk_provider_unavailable",
      }),
    ).toEqual(["banned_ip_match", "risk_provider_unavailable"]);
  });

  it("prefers API review_reasons when present", () => {
    expect(
      deriveManualReviewReasons({
        review_reasons: ["vpn_or_proxy", "banned_ip_match"],
        shared_ip_detected: true,
      }),
    ).toEqual(["vpn_or_proxy", "banned_ip_match"]);
  });
});

describe("manualReviewReasonLabel", () => {
  it("localizes banned IP match in Turkish", () => {
    expect(manualReviewReasonLabel("banned_ip_match", "tr")).toContain(
      "ban kaçırma",
    );
  });
});
