import { describe, expect, it } from "vitest";
import {
  DEFAULT_VERIFICATION_CONFIG,
  deriveVerificationState,
  type VerificationConfig,
} from "@/stores/verification-store";

function config(
  enabled: boolean,
  vpn: boolean,
  shared: boolean
): VerificationConfig {
  return {
    ...DEFAULT_VERIFICATION_CONFIG,
    enabled,
    deny_vpn_or_proxy: vpn,
    deny_shared_ip: shared,
  };
}

describe("deriveVerificationState", () => {
  it("master ON forces both detectors ON", () => {
    expect(deriveVerificationState(config(false, false, false), { enabled: true })).toEqual(
      { enabled: true, deny_vpn_or_proxy: true, deny_shared_ip: true }
    );
  });

  it("master OFF forces both detectors OFF", () => {
    expect(deriveVerificationState(config(true, true, true), { enabled: false })).toEqual(
      { enabled: false, deny_vpn_or_proxy: false, deny_shared_ip: false }
    );
  });

  it("turning one detector off keeps master on", () => {
    expect(
      deriveVerificationState(config(true, true, true), {
        deny_vpn_or_proxy: false,
      })
    ).toEqual({ enabled: true, deny_vpn_or_proxy: false, deny_shared_ip: true });
  });

  it("turning off the last detector auto-disables master", () => {
    expect(
      deriveVerificationState(config(true, false, true), {
        deny_shared_ip: false,
      })
    ).toEqual({ enabled: false, deny_vpn_or_proxy: false, deny_shared_ip: false });
  });

  it("turning a detector on re-enables master", () => {
    expect(
      deriveVerificationState(config(false, false, false), {
        deny_shared_ip: true,
      })
    ).toEqual({ enabled: true, deny_vpn_or_proxy: false, deny_shared_ip: true });
  });
});
