/** Authoring storage cap for TinyMCE-backed markdown (mirrors API). */
export const MAX_STORED_MARKDOWN_CHARS = 100_000;

export const DISCORD_DELIVERY_LIMITS = {
  content: 2000,
  embedDescription: 4096,
  embedTitle: 256,
  embedFooter: 2048,
  fieldName: 256,
  fieldValue: 1024,
  embedFields: 25,
  total: 6000,
  maxEmbedsPerMessage: 10,
  maxMessagesPerDelivery: 5,
} as const;

export type CompileError = {
  code: string;
  message: string;
};

export type DiscordMessagePayload = {
  content?: string;
  embeds?: Array<Record<string, unknown>>;
};

export type CompileResult = {
  payloads: DiscordMessagePayload[];
  warnings: string[];
  errors: CompileError[];
};

function splitMarkdown(text: string, limit: number): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  if (trimmed.length <= limit) return [trimmed];

  const chunks: string[] = [];
  let remaining = trimmed;

  while (remaining) {
    if (remaining.length <= limit) {
      chunks.push(remaining.trim());
      break;
    }

    const window = remaining.slice(0, limit + 1);
    let splitAt = -1;

    for (const marker of ["\n\n", "\n#", "\n-", "\n*", "\n1.", "\n"]) {
      const idx = window.lastIndexOf(marker);
      if (idx > limit / 4) {
        splitAt = idx + marker.length;
        break;
      }
    }

    if (splitAt <= 0) splitAt = limit;

    let candidate = remaining.slice(0, splitAt).trimEnd();
    if (!candidate) {
      candidate = remaining.slice(0, limit);
      splitAt = limit;
    }

    chunks.push(candidate);
    remaining = remaining.slice(splitAt).trimStart();
  }

  return chunks.filter(Boolean);
}

/** Preview-oriented compile: mirrors backend semantic chunking. */
export function compileForPreview(
  content: string,
  embed?: { description?: string; title?: string } | null,
): CompileResult {
  const errors: CompileError[] = [];
  const desc = embed?.description?.trim() ?? "";
  const body = content.trim();
  const descParts = desc ? splitMarkdown(desc, DISCORD_DELIVERY_LIMITS.embedDescription) : [];
  const contentParts = body ? splitMarkdown(body, DISCORD_DELIVERY_LIMITS.content) : [];
  const segmentCount = Math.max(descParts.length, contentParts.length, desc || body ? 1 : 0);

  if (segmentCount > DISCORD_DELIVERY_LIMITS.maxMessagesPerDelivery) {
    return {
      payloads: [],
      warnings: [],
      errors: [
        {
          code: "content_too_long_for_delivery",
          message: `Content requires ${segmentCount} messages but the limit is ${DISCORD_DELIVERY_LIMITS.maxMessagesPerDelivery}.`,
        },
      ],
    };
  }

  if (segmentCount === 0) {
    return { payloads: [], warnings: [], errors: [] };
  }

  const payloads: DiscordMessagePayload[] = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const payload: DiscordMessagePayload = {};
    const partContent = contentParts[index]?.trim();
    if (partContent) payload.content = partContent;
    const partDesc = descParts[index]?.trim();
    if (partDesc || (index === 0 && embed?.title)) {
      payload.embeds = [
        {
          title: index === 0 ? embed?.title : undefined,
          description: partDesc || undefined,
        },
      ];
    }
    if (Object.keys(payload).length > 0) payloads.push(payload);
  }

  return { payloads, warnings: [], errors };
}
