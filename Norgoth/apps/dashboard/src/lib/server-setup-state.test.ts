import { describe, expect, it } from "vitest";
import {
  setupStateAction,
  isSetupState,
  resolveSetupState,
} from "./server-setup-state";

describe("setupStateAction", () => {
  it("maps binary selector states to a single primary action", () => {
    expect(setupStateAction("not_installed")).toBe("install");
    expect(setupStateAction("installed")).toBe("open");
  });

  it("narrows unknown values", () => {
    expect(isSetupState("installed")).toBe(true);
    expect(isSetupState("not_installed")).toBe(true);
    expect(isSetupState("configured")).toBe(false);
    expect(isSetupState("not_configured")).toBe(false);
    expect(isSetupState("bot_installed")).toBe(false);
  });
});

describe("resolveSetupState", () => {
  it("uses bot_installed as the source of truth", () => {
    expect(
      resolveSetupState({ setup_state: "not_installed", bot_installed: true })
    ).toBe("installed");
    expect(
      resolveSetupState({ setup_state: "installed", bot_installed: false })
    ).toBe("not_installed");
  });

  it("ignores legacy configured states when bot_installed is present", () => {
    expect(
      resolveSetupState({ setup_state: "configured", bot_installed: true })
    ).toBe("installed");
    expect(
      resolveSetupState({ setup_state: "not_configured", bot_installed: true })
    ).toBe("installed");
    expect(
      resolveSetupState({ setup_state: "not_configured", bot_installed: false })
    ).toBe("not_installed");
  });

  it("falls back to setup_state or not_installed without bot_installed", () => {
    expect(resolveSetupState({ setup_state: "installed" })).toBe("installed");
    expect(resolveSetupState({ setup_state: "not_installed" })).toBe(
      "not_installed"
    );
    expect(resolveSetupState({ setup_state: "not_configured" })).toBe(
      "not_installed"
    );
    expect(resolveSetupState({})).toBe("not_installed");
  });
});
