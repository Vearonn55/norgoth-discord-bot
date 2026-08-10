import { describe, expect, it } from "vitest";
import { parseTranscript } from "@/components/tickets/transcript-conversation";

describe("parseTranscript", () => {
  it("returns an empty list for blank / placeholder transcripts", () => {
    expect(parseTranscript("")).toEqual([]);
    expect(parseTranscript("(no messages)")).toEqual([]);
    expect(parseTranscript("   ")).toEqual([]);
  });

  it("parses a standard message line into author/timestamp/content", () => {
    const rows = parseTranscript(
      "[2026-08-09 12:00:01] Alice: Hello support"
    );
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      timestamp: "2026-08-09 12:00:01",
      author: "Alice",
      content: "Hello support",
      hasEmbed: false,
      attachments: [],
    });
  });

  it("detects the [embed] marker and strips it from content", () => {
    const rows = parseTranscript(
      "[2026-08-09 12:00:02] Bot: Welcome [embed]"
    );
    expect(rows[0].hasEmbed).toBe(true);
    expect(rows[0].content).toBe("Welcome");
  });

  it("extracts Discord CDN attachment URLs from the content", () => {
    const url =
      "https://cdn.discordapp.com/attachments/1/2/file.png";
    const rows = parseTranscript(
      `[2026-08-09 12:00:03] Bob: see this ${url}`
    );
    expect(rows[0].attachments).toEqual([url]);
    expect(rows[0].content).toBe("see this");
  });

  it("keeps non-matching lines as system rows", () => {
    const rows = parseTranscript("corrupted line without stamp");
    expect(rows).toHaveLength(1);
    expect(rows[0].author).toBe("System");
    expect(rows[0].content).toBe("corrupted line without stamp");
  });

  it("parses a multi-message conversation in order", () => {
    const raw = [
      "[2026-08-09 12:00:01] Alice: hi",
      "[2026-08-09 12:00:05] Support: hello",
      "[2026-08-09 12:01:00] Alice: thanks",
    ].join("\n");
    const rows = parseTranscript(raw);
    expect(rows.map((r) => r.author)).toEqual([
      "Alice",
      "Support",
      "Alice",
    ]);
  });
});
