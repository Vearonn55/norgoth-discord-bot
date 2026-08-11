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
};

export function MessagePreview({
  content,
  embed,
  showEmbed = false,
  mode = "auto",
  showContentWithEmbed = false,
  onPickMedia,
}: MessagePreviewProps) {
  const color = parseEmbedColor(embed?.color) ?? 0x5865f2;
  const colorHex = `#${color.toString(16).padStart(6, "0")}`;
  const interactive = typeof onPickMedia === "function";
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
                {embed.author?.name ? (
                  <div className="d-flex align-items-center gap-2 mb-1">
                    {embed.author.icon_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={embed.author.icon_url}
                        alt=""
                        className="rounded-circle"
                        style={{ width: 20, height: 20, objectFit: "cover" }}
                      />
                    ) : null}
                    <span className="small fw-semibold text-white text-break">
                      {embed.author.name}
                    </span>
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
              onPick={onPickMedia}
              banner
            />

            {embed.footer ? (
              <div className="d-flex align-items-center gap-2 mt-2">
                {embed.footer_icon_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={embed.footer_icon_url}
                    alt=""
                    className="rounded-circle"
                    style={{ width: 16, height: 16, objectFit: "cover" }}
                  />
                ) : null}
                <div className="small text-body-tertiary text-break">
                  {embed.footer}
                </div>
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

function MediaSlotView({
  slot,
  url,
  interactive,
  onPick,
  banner = false,
}: {
  slot: MediaSlot;
  url?: string;
  interactive: boolean;
  onPick?: (slot: MediaSlot) => void;
  banner?: boolean;
}) {
  const label = slot === "thumbnail" ? "Thumbnail" : "Main image";
  const sizeStyle = banner
    ? { width: "100%", maxHeight: 220 }
    : { width: 72, height: 72 };

  if (url) {
    const img = (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={url}
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

  if (!interactive) return null;

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
