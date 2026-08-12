import { describe, expect, it } from "vitest";
import { setupStateAction, isSetupState } from "./server-setup-state";

describe("setupStateAction", () => {
  it("maps selector states to a single primary action", () => {
    expect(setupStateAction("not_installed")).toBe("install");
    expect(setupStateAction("not_configured")).toBe("configure");
    expect(setupStateAction("configured")).toBe("open");
  });

  it("narrows unknown values", () => {
    expect(isSetupState("configured")).toBe(true);
    expect(isSetupState("bot_installed")).toBe(false);
  });
});
