import { describe, expect, it } from "vitest";
import { resolveChannelLabel } from "@/stores/logging-config-store";

const live = [
  { id: "111", name: "mod-log" },
  { id: "222", name: "member-log" },
];

describe("resolveChannelLabel", () => {
  it("prefers the live Discord channel name", () => {
    expect(
      resolveChannelLabel({ channel_id: "111", name: "stale" }, live)
    ).toBe("#mod-log");
  });

  it("falls back to the persisted config name when not live-resolvable", () => {
    expect(
      resolveChannelLabel({ channel_id: "999", name: "audit-log" }, live)
    ).toBe("#audit-log");
  });

  it("never renders the raw channel ID as a label", () => {
    // Simulates the old corruption: persisted name equals the raw ID.
    const label = resolveChannelLabel(
      { channel_id: "999", name: "999" },
      live
    );
    expect(label).toBe("Unknown channel");
    expect(label).not.toContain("999");
  });

  it("shows Unknown channel when a channel_id cannot be resolved and no name", () => {
    expect(
      resolveChannelLabel({ channel_id: "999", name: "" }, live)
    ).toBe("Unknown channel");
  });

  it("shows Not provisioned when there is no channel_id", () => {
    expect(
      resolveChannelLabel({ channel_id: null, name: "" }, live)
    ).toBe("Not provisioned");
  });

  it("stays stable regardless of the live cache being empty", () => {
    expect(
      resolveChannelLabel({ channel_id: "111", name: "mod-log" }, [])
    ).toBe("#mod-log");
  });
});
