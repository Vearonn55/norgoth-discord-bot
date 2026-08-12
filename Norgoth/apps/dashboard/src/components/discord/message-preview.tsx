"use client";

import { discordMarkdownToHtml } from "@/lib/discord-markdown";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";
import { parseEmbedColor } from "@/lib/discord/message-payload";

type MediaSlot = "thumbnail" | "image";

export type MessagePreviewMode = "text" | "embed" | "auto";

type MessagePreviewProps = {
  content?: string;
  embed?: DiscordEmbedPayload | null;
  showEmbed?: boolean;
  /**
   * Controls which preview slots render.
   * - text: content only
   * - embed: embed card only (optional content above when showContentWithEmbed)
   * - auto: legacy dual layout (content slot always, embed when showEmbed)
   */
  mode?: MessagePreviewMode;
  /**
   * When mode is "embed", allow non-empty Discord message content above the
   * embed (Embed Library). Empty content never shows “No message content”.
   */
  showContentWithEmbed?: boolean;
  /**
   * When provided, empty media slots render as clickable placeholders and
   * existing media becomes clickable to replace. Enables in-preview uploads.
   */
  onPickMedia?: (slot: MediaSlot) => void;
  /**
   * Editor-only: reserve author/thumbnail/image/footer icon slots with subdued
   * placeholders. Never writes URLs into embed state or Discord payloads.
   */
  showImagePlaceholders?: boolean;
};

function hasUrl(value?: string | null): boolean {
  return Boolean(typeof value === "string" && value.trim());
}

export function MessagePreview({
  content,
  embed,
  showEmbed = false,
  mode = "auto",
  showContentWithEmbed = false,
  onPickMedia,
  showImagePlaceholders = false,
}: MessagePreviewProps) {
  const color = parseEmbedColor(embed?.color) ?? 0x5865f2;
  const colorHex = `#${color.toString(16).padStart(6, "0")}`;
  const interactive = typeof onPickMedia === "function";
  const showPlaceholders = showImagePlaceholders || interactive;
  const trimmed = content?.trim() ?? "";

  const renderEmbed =
    mode === "embed" ? Boolean(embed) : mode === "auto" && showEmbed && Boolean(embed);

  // Embed-only mode never paints the empty “No message content” placeholder.
  const showContentSlot =
    mode === "text"
      ? true
      : mode === "embed"
        ? showContentWithEmbed && Boolean(trimmed)
        : true; // auto: legacy always-on content slot

  const authorName = embed?.author?.name?.trim() ?? "";
  const authorIcon = embed?.author?.icon_url;
  const footerText = embed?.footer?.trim() ?? "";
  const footerIcon = embed?.footer_icon_url;
  const showAuthorRow = Boolean(authorName) || (showPlaceholders && hasUrl(authorIcon));
  const showAuthorPlaceholder = showPlaceholders && Boolean(authorName) && !hasUrl(authorIcon);
  const showFooterRow = Boolean(footerText) || (showPlaceholders && hasUrl(footerIcon));
  const showFooterPlaceholder = showPlaceholders && Boolean(footerText) && !hasUrl(footerIcon);

  return (
    <div className="norgoth-discord-preview border rounded p-3">
      <div className="small text-uppercase fw-semibold text-body-secondary mb-2">
        Live preview
      </div>
      {showContentSlot ? (
        trimmed ? (
          <div
            className={`prose-preview ${renderEmbed ? "mb-3" : ""}`}
            dangerouslySetInnerHTML={{
              __html: discordMarkdownToHtml(trimmed),
            }}
          />
        ) : mode === "auto" || mode === "text" ? (
          <p
            className={`small text-body-secondary ${renderEmbed ? "mb-3" : "mb-0"}`}
          >
            No message content
          </p>
        ) : null
      ) : null}

      {renderEmbed && embed ? (
        <div
          className="norgoth-discord-embed rounded"
          style={{ borderLeft: `4px solid ${colorHex}` }}
        >
          <div className="p-3">
            <div className="d-flex justify-content-between gap-3">
              <div className="flex-grow-1 min-w-0">
                {showAuthorRow ? (
                  <div className="d-flex align-items-center gap-2 mb-1">
                    {hasUrl(authorIcon) ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={authorIcon!.trim()}
                        alt=""
                        className="rounded-circle"
                        style={{ width: 20, height: 20, objectFit: "cover" }}
                      />
                    ) : showAuthorPlaceholder ? (
                      <IconPlaceholder size={20} label="Author icon" />
                    ) : null}
                    {authorName ? (
                      <span className="small fw-semibold text-white text-break">
                        {authorName}
                      </span>
                    ) : null}
                  </div>
                ) : null}
                {embed.title ? (
                  <div className="fw-semibold text-white mb-1 text-break">
                    {embed.title}
                  </div>
                ) : null}
                {embed.description ? (
                  <div className="small text-body-secondary white-space-pre-wrap text-break">
                    {embed.description}
                  </div>
                ) : null}
              </div>
              <MediaSlotView
                slot="thumbnail"
                url={embed.thumbnail_url}
                interactive={interactive}
                showPlaceholder={showPlaceholders}
                onPick={onPickMedia}
              />
            </div>

            {embed.fields && embed.fields.length > 0 ? (
              <div className="row g-2 mt-2">
                {embed.fields.map((field, i) => (
                  <div key={i} className={field.inline ? "col-6" : "col-12"}>
                    <div className="small fw-semibold text-white text-break">
                      {field.name || "Field"}
                    </div>
                    <div className="small text-body-secondary text-break">
                      {field.value || "—"}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <MediaSlotView
              slot="image"
              url={embed.image_url}
              interactive={interactive}
              showPlaceholder={showPlaceholders}
              onPick={onPickMedia}
              banner
            />

            {showFooterRow ? (
              <div className="d-flex align-items-center gap-2 mt-2">
                {hasUrl(footerIcon) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={footerIcon!.trim()}
                    alt=""
                    className="rounded-circle"
                    style={{ width: 16, height: 16, objectFit: "cover" }}
                  />
                ) : showFooterPlaceholder ? (
                  <IconPlaceholder size={16} label="Footer icon" />
                ) : null}
                {footerText ? (
                  <div className="small text-body-tertiary text-break">
                    {footerText}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {mode === "embed" && !embed ? (
        <p className="small text-body-secondary mb-0">No embed to preview.</p>
      ) : null}
    </div>
  );
}

function IconPlaceholder({ size, label }: { size: number; label: string }) {
  return (
    <span
      className="norgoth-embed-icon-placeholder rounded-circle flex-shrink-0 border border-dashed border-secondary"
      style={{
        width: size,
        height: size,
        display: "inline-block",
        background: "rgba(241, 244, 250, 0.06)",
      }}
      title={label}
      aria-hidden="true"
    >
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

function MediaSlotView({
  slot,
  url,
  interactive,
  showPlaceholder,
  onPick,
  banner = false,
}: {
  slot: MediaSlot;
  url?: string;
  interactive: boolean;
  showPlaceholder: boolean;
  onPick?: (slot: MediaSlot) => void;
  banner?: boolean;
}) {
  const label = slot === "thumbnail" ? "Thumbnail" : "Main image";
  const sizeStyle = banner
    ? { width: "100%", maxHeight: 220 }
    : { width: 72, height: 72 };
  const trimmed = typeof url === "string" ? url.trim() : "";

  if (trimmed) {
    const img = (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={trimmed}
        alt={label}
        className="rounded"
        style={{ ...sizeStyle, objectFit: "cover" }}
      />
    );
    if (!interactive) {
      return banner ? <div className="mt-3">{img}</div> : <div className="flex-shrink-0">{img}</div>;
    }
    return (
      <button
        type="button"
        onClick={() => onPick?.(slot)}
        className={`btn btn-link p-0 border-0 ${banner ? "mt-3 d-block w-100" : "flex-shrink-0"}`}
        title={`Replace ${label.toLowerCase()}`}
        style={banner ? undefined : { lineHeight: 0 }}
      >
        {img}
      </button>
    );
  }

  if (!showPlaceholder) return null;

  if (interactive) {
    return (
      <button
        type="button"
        onClick={() => onPick?.(slot)}
        className={`norgoth-embed-placeholder btn btn-outline-secondary border-dashed d-flex flex-column align-items-center justify-content-center text-body-secondary ${banner ? "mt-3 w-100" : "flex-shrink-0"}`}
        style={banner ? { minHeight: 90 } : { width: 72, height: 72, padding: 4 }}
        title={`Add ${label.toLowerCase()}`}
      >
        <span className="small fw-semibold">{label}</span>
        <span className="text-body-tertiary" style={{ fontSize: banner ? 12 : 10 }}>
          Click to upload or use URL
        </span>
      </button>
    );
  }

  return (
    <div
      className={`norgoth-embed-placeholder border border-dashed border-secondary rounded d-flex flex-column align-items-center justify-content-center text-body-secondary ${banner ? "mt-3 w-100" : "flex-shrink-0"}`}
      style={
        banner
          ? { minHeight: 90, background: "rgba(241, 244, 250, 0.04)" }
          : { width: 72, height: 72, padding: 4, background: "rgba(241, 244, 250, 0.04)" }
      }
      aria-hidden="true"
    >
      <span className="small fw-semibold">{label}</span>
      <span className="visually-hidden">{label} placeholder</span>
    </div>
  );
}
