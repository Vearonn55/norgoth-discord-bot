/**
 * Discord message payload helpers for content + embed announcements.
 */

export type DiscordEmbedField = {
  name: string;
  value: string;
  inline?: boolean;
};

export type DiscordEmbedAuthor = {
  name?: string;
  url?: string;
  icon_url?: string;
};

export type DiscordEmbedPayload = {
  title?: string;
  description?: string;
  color?: number | string | null;
  footer?: string;
  footer_icon_url?: string;
  author?: DiscordEmbedAuthor;
  thumbnail_url?: string;
  image_url?: string;
  fields?: DiscordEmbedField[];
};

export const DISCORD_LIMITS = {
  content: 2000,
  embedTitle: 256,
  embedDescription: 4096,
  embedFooter: 2048,
  embedFields: 25,
  fieldName: 256,
  fieldValue: 1024,
  authorName: 256,
  total: 6000,
} as const;

export function parseEmbedColor(color: number | string | null | undefined): number | null {
  if (color == null || color === "") return null;
  if (typeof color === "number") return color > 0 ? color : null;
  const raw = color.trim().replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(raw)) return null;
  return parseInt(raw, 16);
}

export function substitutePlaceholders(
  template: string,
  values: Record<string, string>
): string {
  let out = template;
  for (const [key, value] of Object.entries(values)) {
    out = out.replaceAll(`{${key}}`, value);
  }
  return out;
}

export function embedTotalCharacters(embed: DiscordEmbedPayload): number {
  let total = 0;
  total += embed.title?.length ?? 0;
  total += embed.description?.length ?? 0;
  total += embed.footer?.length ?? 0;
  total += embed.author?.name?.length ?? 0;
  for (const field of embed.fields ?? []) {
    total += field.name.length + field.value.length;
  }
  return total;
}

/** Omit empty/whitespace image URL fields so drafts never persist `""`. */
export function scrubEmptyEmbedUrls(
  embed: DiscordEmbedPayload
): DiscordEmbedPayload {
  const next: DiscordEmbedPayload = { ...embed };

  const clean = (value?: string): string | undefined => {
    if (typeof value !== "string") return undefined;
    const trimmed = value.trim();
    return trimmed || undefined;
  };

  const thumbnail = clean(next.thumbnail_url);
  if (thumbnail) next.thumbnail_url = thumbnail;
  else delete next.thumbnail_url;

  const image = clean(next.image_url);
  if (image) next.image_url = image;
  else delete next.image_url;

  const footerIcon = clean(next.footer_icon_url);
  if (footerIcon) next.footer_icon_url = footerIcon;
  else delete next.footer_icon_url;

  if (next.author) {
    const author = { ...next.author };
    const icon = clean(author.icon_url);
    if (icon) author.icon_url = icon;
    else delete author.icon_url;
    const url = clean(author.url);
    if (url) author.url = url;
    else delete author.url;
    next.author = author;
  }

  return next;
}

export function validateEmbed(embed: DiscordEmbedPayload): string[] {
  const errors: string[] = [];
  if (embed.title && embed.title.length > DISCORD_LIMITS.embedTitle) {
    errors.push(`Title exceeds ${DISCORD_LIMITS.embedTitle} characters`);
  }
  if (
    embed.description &&
    embed.description.length > DISCORD_LIMITS.embedDescription
  ) {
    errors.push(
      `Description exceeds ${DISCORD_LIMITS.embedDescription} characters`
    );
  }
  if (embed.footer && embed.footer.length > DISCORD_LIMITS.embedFooter) {
    errors.push(`Footer exceeds ${DISCORD_LIMITS.embedFooter} characters`);
  }
  if (
    embed.author?.name &&
    embed.author.name.length > DISCORD_LIMITS.authorName
  ) {
    errors.push(`Author name exceeds ${DISCORD_LIMITS.authorName} characters`);
  }
  if ((embed.fields?.length ?? 0) > DISCORD_LIMITS.embedFields) {
    errors.push(`Max ${DISCORD_LIMITS.embedFields} fields`);
  }
  (embed.fields ?? []).forEach((field, index) => {
    if (field.name.length > DISCORD_LIMITS.fieldName) {
      errors.push(`Field ${index + 1} name exceeds ${DISCORD_LIMITS.fieldName} characters`);
    }
    if (field.value.length > DISCORD_LIMITS.fieldValue) {
      errors.push(`Field ${index + 1} value exceeds ${DISCORD_LIMITS.fieldValue} characters`);
    }
  });
  if (embedTotalCharacters(embed) > DISCORD_LIMITS.total) {
    errors.push(`Embed exceeds the ${DISCORD_LIMITS.total}-character total limit`);
  }
  return errors;
}
