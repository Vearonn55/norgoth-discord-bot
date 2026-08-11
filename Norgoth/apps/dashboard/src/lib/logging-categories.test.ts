import { describe, expect, it } from "vitest";
import { mergeLoggingCategories } from "@/lib/logging-categories";
import type {
  LoggingCatalog,
  LoggingConfig,
} from "@/stores/logging-config-store";

const catalog: LoggingCatalog = {
  groups: [
    {
      key: "member",
      label: "Members",
      default_color: 0x2ecc71,
      events: [{ event_type: "member_join", label: "Member joined" }],
    },
    {
      key: "voice",
      label: "Voice",
      default_color: 0x1abc9c,
      events: [{ event_type: "voice_join", label: "Joined voice" }],
    },
  ],
};

const config: LoggingConfig = {
  id: "cfg-1",
  guild_id: "1",
  enabled: true,
  status: "active",
  category_id: null,
  category_name: null,
  norgoth_managed_category: false,
  channels: [
    {
      id: "ch-1",
      key: "member",
      name: "member-logs",
      channel_id: "99",
      norgoth_managed: true,
      default_color: 0x2ecc71,
      position: 0,
      enabled: true,
    },
  ],
  events: [
    {
      event_type: "member_join",
      channel_key: "member",
      color: null,
      enabled: true,
    },
  ],
};

describe("mergeLoggingCategories", () => {
  it("includes every catalog group even when guild has fewer rows", () => {
    const cards = mergeLoggingCategories(catalog, config);
    expect(cards.map((c) => c.key)).toEqual(["member", "voice"]);
    expect(cards[0]?.configured).toBe(true);
    expect(cards[0]?.enabled).toBe(true);
    expect(cards[1]?.configured).toBe(false);
    expect(cards[1]?.enabled).toBe(false);
    expect(cards[1]?.channel_id).toBeNull();
  });

  it("does not duplicate when all groups are configured", () => {
    const full: LoggingConfig = {
      ...config,
      channels: [
        ...config.channels,
        {
          key: "voice",
          name: "voice-logs",
          channel_id: null,
          norgoth_managed: true,
          default_color: 0x1abc9c,
          position: 1,
          enabled: false,
        },
      ],
    };
    const cards = mergeLoggingCategories(catalog, full);
    expect(cards).toHaveLength(2);
    expect(cards.every((c) => c.configured)).toBe(true);
  });

  it("returns empty when catalog and config are missing", () => {
    expect(mergeLoggingCategories(null, null)).toEqual([]);
  });
});
