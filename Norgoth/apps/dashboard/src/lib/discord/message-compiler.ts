/** Authoring storage cap for TinyMCE-backed markdown (mirrors API). */
export const MAX_STORED_MARKDOWN_CHARS = 100_000;

export const DISCORD_DELIVERY_LIMITS = {
  content: 2000,
  embedDescription: 4096,
  embedTitle: 256,
  embedFooter: 2048,
  fieldName: 256,
  fieldValue: 1024,
  authorName: 256,
  embedFields: 25,
  total: 6000,
  maxEmbedsPerMessage: 10,
  maxMessagesPerDelivery: 5,
} as const;

export type CompileError = {
  code: string;
  message: string;
};

export type PreviewEmbed = {
  title?: string;
  description?: string;
  color?: number | string | null;
  footer?: string;
  footer_icon_url?: string;
  author?: { name?: string; url?: string; icon_url?: string };
  thumbnail_url?: string;
  image_url?: string;
  fields?: Array<{ name: string; value: string; inline?: boolean }>;
};

export type DiscordMessagePayload = {
  content?: string;
  embeds?: PreviewEmbed[];
};

export type CompileResult = {
  payloads: DiscordMessagePayload[];
  warnings: string[];
  errors: CompileError[];
};

function cappedLen(value: string | null | undefined, cap: number): number {
  const trimmed = value?.trim() ?? "";
  return trimmed ? Math.min(trimmed.length, cap) : 0;
}

function fieldsChars(
  fields: PreviewEmbed["fields"] | undefined,
): number {
  if (!fields?.length) return 0;
  return fields.slice(0, DISCORD_DELIVERY_LIMITS.embedFields).reduce((sum, field) => {
    return (
      sum +
      Math.min(field.name.length, DISCORD_DELIVERY_LIMITS.fieldName) +
      Math.min(field.value.length, DISCORD_DELIVERY_LIMITS.fieldValue)
    );
  }, 0);
}

function chromeChars(
  embed: PreviewEmbed,
  opts: {
    title: boolean;
    author: boolean;
    fields: boolean;
    footer: boolean;
  },
): number {
  let total = 0;
  if (opts.title) total += cappedLen(embed.title, DISCORD_DELIVERY_LIMITS.embedTitle);
  if (opts.author) total += cappedLen(embed.author?.name, DISCORD_DELIVERY_LIMITS.authorName);
  if (opts.fields) total += fieldsChars(embed.fields);
  if (opts.footer) total += cappedLen(embed.footer, DISCORD_DELIVERY_LIMITS.embedFooter);
  return total;
}

export function splitMarkdown(
  text: string,
  limit: number,
  firstLimit?: number,
): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  if (firstLimit === undefined && trimmed.length <= limit) return [trimmed];

  const chunks: string[] = [];
  let remaining = trimmed;
  let currentLimit = firstLimit ?? limit;

  while (remaining) {
    const thisLimit = currentLimit > 0 ? currentLimit : limit;
    currentLimit = limit;
    if (remaining.length <= thisLimit) {
      chunks.push(remaining.trim());
      break;
    }

    const window = remaining.slice(0, thisLimit + 1);
    let splitAt = -1;

    for (const marker of ["\n\n", "\n#", "\n-", "\n*", "\n1.", "\n"]) {
      const idx = window.lastIndexOf(marker);
      if (idx > thisLimit / 4) {
        splitAt = idx + marker.length;
        break;
      }
    }

    if (splitAt <= 0) splitAt = thisLimit;

    let candidate = remaining.slice(0, splitAt).trimEnd();
    if (!candidate) {
      candidate = remaining.slice(0, thisLimit);
      splitAt = thisLimit;
    }

    chunks.push(candidate);
    remaining = remaining.slice(splitAt).trimStart();
  }

  return chunks.filter(Boolean);
}

function previewEmbedChars(embed: PreviewEmbed): number {
  return (
    (embed.title?.length ?? 0) +
    (embed.description?.length ?? 0) +
    (embed.footer?.length ?? 0) +
    (embed.author?.name?.length ?? 0) +
    fieldsChars(embed.fields)
  );
}

function packEmbedGroups(cards: PreviewEmbed[]): PreviewEmbed[][] {
  const groups: PreviewEmbed[][] = [];
  let current: PreviewEmbed[] = [];
  let currentChars = 0;
  for (const card of cards) {
    const chars = previewEmbedChars(card);
    const overflowCount = current.length >= DISCORD_DELIVERY_LIMITS.maxEmbedsPerMessage;
    const overflowChars =
      current.length > 0 && currentChars + chars > DISCORD_DELIVERY_LIMITS.total;
    if (overflowCount || overflowChars) {
      groups.push(current);
      current = [];
      currentChars = 0;
    }
    current.push(card);
    currentChars += chars;
  }
  if (current.length) groups.push(current);
  return groups;
}

/** Preview-oriented compile: mirrors backend stacked-embed chunking. */
export function compileForPreview(
  content: string,
  embed?: PreviewEmbed | null,
): CompileResult {
  const body = content.trim();
  const source: PreviewEmbed = embed ?? {};
  const desc = source.description?.trim() ?? "";
  const hasChrome = Boolean(
    source.title?.trim() ||
      source.author?.name?.trim() ||
      (source.fields?.length ?? 0) > 0 ||
      source.footer?.trim() ||
      hasMedia(source.thumbnail_url) ||
      hasMedia(source.image_url),
  );

  const firstChrome = chromeChars(source, {
    title: true,
    author: true,
    fields: true,
    footer: false,
  });
  let firstDescBudget = Math.min(
    DISCORD_DELIVERY_LIMITS.embedDescription,
    Math.max(0, DISCORD_DELIVERY_LIMITS.total - firstChrome),
  );

  let descParts = desc ? splitMarkdown(desc, DISCORD_DELIVERY_LIMITS.embedDescription, firstDescBudget) : [];
  const footerChars = cappedLen(source.footer, DISCORD_DELIVERY_LIMITS.embedFooter);
  if (
    descParts.length === 1 &&
    footerChars &&
    firstChrome + descParts[0].length + footerChars > DISCORD_DELIVERY_LIMITS.total
  ) {
    firstDescBudget = Math.max(0, DISCORD_DELIVERY_LIMITS.total - firstChrome);
    descParts = splitMarkdown(desc, DISCORD_DELIVERY_LIMITS.embedDescription, firstDescBudget);
  }

  const contentParts = body ? splitMarkdown(body, DISCORD_DELIVERY_LIMITS.content) : [];

  if (!descParts.length && !contentParts.length && !hasChrome) {
    return { payloads: [], warnings: [], errors: [] };
  }

  const embedCards: PreviewEmbed[] = [];
  if (descParts.length || hasChrome) {
    const lastIndex = Math.max(descParts.length - 1, 0);
    const count = Math.max(descParts.length, hasChrome ? 1 : 0);
    for (let index = 0; index < count; index += 1) {
      const isFirst = index === 0;
      const isLast = index === lastIndex || (!descParts.length && isFirst);
      const partDesc = descParts[index]?.trim() ?? "";
      const card: PreviewEmbed = { color: source.color };
      if (partDesc) card.description = partDesc;
      if (isFirst) {
        if (source.title) card.title = source.title;
        if (source.author) card.author = source.author;
        if (source.thumbnail_url) card.thumbnail_url = source.thumbnail_url;
        if (source.image_url) card.image_url = source.image_url;
        if (source.fields) card.fields = source.fields;
      }
      if (isLast) {
        if (source.footer) card.footer = source.footer;
        if (source.footer_icon_url) card.footer_icon_url = source.footer_icon_url;
      }
      embedCards.push(card);
    }
  }

  const embedGroups: PreviewEmbed[][] = embedCards.length
    ? packEmbedGroups(embedCards)
    : [[]];

  const parts = contentParts.length ? [...contentParts] : [""];
  const segmentCount = Math.max(parts.length, embedGroups.length, 1);
  while (parts.length < segmentCount) parts.push("");
  while (embedGroups.length < segmentCount) embedGroups.push([]);

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

  const payloads: DiscordMessagePayload[] = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const payload: DiscordMessagePayload = {};
    const partContent = parts[index]?.trim();
    if (partContent) payload.content = partContent;
    if (embedGroups[index]?.length) payload.embeds = embedGroups[index];
    if (payload.content || payload.embeds?.length) payloads.push(payload);
  }

  return { payloads, warnings: [], errors: [] };
}
