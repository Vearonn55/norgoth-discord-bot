import { describe, expect, it } from "vitest";
import { isValidAutoResponseMarkdown } from "@/lib/auto-response-validation";

describe("auto response markdown validation", () => {
  it("rejects empty scaffolding after TinyMCE → markdown", () => {
    // htmlToDiscordMarkdown("<p><br></p>") yields "" in the browser.
    expect(isValidAutoResponseMarkdown("").ok).toBe(false);
    expect(isValidAutoResponseMarkdown("   ").ok).toBe(false);
    expect(isValidAutoResponseMarkdown("\n\n").reason).toBe("empty");
  });

  it("rejects over-length markdown", () => {
    expect(isValidAutoResponseMarkdown("x".repeat(1501)).reason).toBe(
      "too_long"
    );
  });

  it("accepts normal markdown including bold markers", () => {
    expect(isValidAutoResponseMarkdown("Hi **{user}**").ok).toBe(true);
  });
});
