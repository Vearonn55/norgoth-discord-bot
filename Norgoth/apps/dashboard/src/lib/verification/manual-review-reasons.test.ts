import { describe, expect, it } from "vitest";
import {
  deriveManualReviewReasons,
  manualReviewReasonHeading,
  manualReviewReasonLabel,
  manualReviewReasonShortLabel,
} from "@/lib/verification/manual-review-reasons";

describe("deriveManualReviewReasons", () => {
  it("returns no reasons when nothing fired", () => {
    expect(
      deriveManualReviewReasons({
        vpn_or_proxy_detected: false,
        shared_ip_detected: false,
        high_risk_guild_detected: false,
      })
    ).toEqual([]);
  });

  it("derives every triggered reason in a stable order", () => {
    expect(
      deriveManualReviewReasons({
        vpn_or_proxy_detected: true,
        shared_ip_detected: true,
        high_risk_guild_detected: true,
      })
    ).toEqual(["vpn_or_proxy", "shared_ip", "high_risk_server"]);
  });

  it("supports multiple signals at once", () => {
    expect(
      deriveManualReviewReasons({
        shared_ip_detected: true,
        high_risk_guild_detected: true,
      })
    ).toEqual(["shared_ip", "high_risk_server"]);
  });
});

describe("manualReviewReasonLabel", () => {
  it("localizes to English by default", () => {
    expect(manualReviewReasonLabel("vpn_or_proxy", "en")).toBe(
      "VPN / Proxy detected"
    );
  });

  it("localizes to Turkish", () => {
    expect(manualReviewReasonLabel("shared_ip", "tr")).toBe(
      "Paylaşılan IP / olası ikincil hesap"
    );
  });

  it("provides short labels and a localized heading", () => {
    expect(manualReviewReasonShortLabel("high_risk_server", "en")).toBe(
      "High Risk"
    );
    expect(manualReviewReasonHeading("tr")).toBe("Manuel inceleme nedeni");
    expect(manualReviewReasonHeading("en")).toBe("Manual review reason");
  });
});
