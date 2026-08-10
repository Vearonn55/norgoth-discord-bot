import { describe, expect, it } from "vitest";
import { newTicketPanel } from "@/stores/tickets-store";

describe("newTicketPanel", () => {
  it("defaults the open-ticket category to null and drops the legacy log field", () => {
    const panel = newTicketPanel();
    expect(panel).toHaveProperty("open_category_id", null);
    // Closed-ticket logging moved to the central Logging Configurations wizard.
    expect(panel).not.toHaveProperty("closed_log_channel_id");
  });

  it("generates a unique id per panel", () => {
    expect(newTicketPanel().id).not.toBe(newTicketPanel().id);
  });
});
