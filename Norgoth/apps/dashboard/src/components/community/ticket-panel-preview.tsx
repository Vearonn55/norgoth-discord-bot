"use client";

import { CSpinner } from "@coreui/react";
import { MessagePreview } from "@/components/discord/message-preview";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";

type TicketPanelPreviewProps = {
  mode?: "text" | "embed";
  content?: string;
  embed?: DiscordEmbedPayload | null;
  buttonLabel: string;
  embedLoading?: boolean;
  embedMissing?: boolean;
  /** True when no draft has been selected yet (embed mode). */
  noDraft?: boolean;
};

/**
 * Composes the shared MessagePreview with Ticket Panel Open Ticket chrome.
 */
export function TicketPanelPreview({
  mode = "embed",
  content,
  embed,
  buttonLabel,
  embedLoading = false,
  embedMissing = false,
  noDraft = false,
}: TicketPanelPreviewProps) {
  return (
    <div className="norgoth-ticket-panel-preview border rounded p-3">
      <div className="small text-uppercase fw-semibold text-body-secondary mb-2">
        Panel preview
      </div>

      {mode === "text" ? (
        <div className="mb-2">
          {content?.trim() ? (
            <MessagePreview content={content} mode="text" />
          ) : (
            <div className="border rounded p-3 small text-body-secondary">
              Write a plain-text message to preview the panel.
            </div>
          )}
        </div>
      ) : embedLoading ? (
        <div className="d-flex align-items-center gap-2 text-body-secondary small py-4">
          <CSpinner size="sm" /> Loading embed draft…
        </div>
      ) : embedMissing ? (
        <div className="border rounded p-3 small text-warning mb-2">
          <div className="fw-semibold">Embed Draft Missing</div>
          <div className="text-body-secondary">
            The selected Embed Library draft no longer exists. Re-select or
            create a draft before publishing.
          </div>
        </div>
      ) : noDraft ? (
        <div className="border rounded p-3 small text-body-secondary mb-2">
          Select From Draft or Create New to preview the panel message.
        </div>
      ) : (
        <div className="mb-2">
          <MessagePreview
            content={content}
            embed={embed}
            mode="embed"
            showContentWithEmbed
            showImagePlaceholders
          />
        </div>
      )}

      <div className="d-flex mt-2">
        <span
          className="btn btn-primary btn-sm"
          style={{ pointerEvents: "none" }}
          aria-hidden
        >
          🎫 {buttonLabel || "Open Ticket"}
        </span>
      </div>
    </div>
  );
}
