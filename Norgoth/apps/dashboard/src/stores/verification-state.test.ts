import { describe, expect, it } from "vitest";
import {
  DEFAULT_VERIFICATION_CONFIG,
  canPublishOrCopy,
  deriveVerificationState,
  hasRequiredBindings,
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

describe("setup gating", () => {
  it("requires all bindings", () => {
    expect(hasRequiredBindings(DEFAULT_VERIFICATION_CONFIG)).toBe(false);
    expect(
      hasRequiredBindings({
        ...DEFAULT_VERIFICATION_CONFIG,
        verification_channel_id: "1",
        log_channel_id: "2",
        unverified_role_id: "3",
        member_role_id: "4",
      })
    ).toBe(true);
  });

  it("gates copy/publish until bindings are persisted", () => {
    expect(canPublishOrCopy(DEFAULT_VERIFICATION_CONFIG)).toBe(false);
    expect(
      canPublishOrCopy({
        ...DEFAULT_VERIFICATION_CONFIG,
        setup_state: "incomplete",
        verification_channel_id: "1",
        log_channel_id: "2",
        unverified_role_id: "3",
        member_role_id: "4",
      })
    ).toBe(false);
    expect(
      canPublishOrCopy({
        ...DEFAULT_VERIFICATION_CONFIG,
        setup_state: "active",
        verification_channel_id: "1",
        log_channel_id: "2",
        unverified_role_id: "3",
        member_role_id: "4",
      })
    ).toBe(true);
    expect(
      canPublishOrCopy({
        ...DEFAULT_VERIFICATION_CONFIG,
        setup_state: "disabled",
        verification_channel_id: "1",
        log_channel_id: "2",
        unverified_role_id: "3",
        member_role_id: "4",
      })
    ).toBe(true);
    expect(
      canPublishOrCopy({
        ...DEFAULT_VERIFICATION_CONFIG,
        setup_state: "not_configured",
        verification_channel_id: "1",
        log_channel_id: "2",
        unverified_role_id: "3",
        member_role_id: "4",
      })
    ).toBe(false);
  });
});
