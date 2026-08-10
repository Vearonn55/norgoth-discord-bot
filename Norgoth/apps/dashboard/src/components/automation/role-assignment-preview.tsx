"use client";

import { CSpinner } from "@coreui/react";
import {
  ROLE_MENU_INTERACTION_LABELS,
  ROLE_MENU_STYLE_SWATCHES,
  type RoleMenuInteraction,
  type RoleMenuStyle,
} from "@/lib/discord/role-menu-modes";
import { emojiPreviewSrc } from "@/lib/discord/emoji-data";
import { MessagePreview } from "@/components/discord/message-preview";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";
import type { RoleMenu } from "@/stores/automation-store";

type RoleAssignmentPreviewProps = {
  menu: Pick<
    RoleMenu,
    "title" | "description" | "interaction" | "roles" | "binding_type"
  >;
  /** Full embed payload of the bound Embed Draft (when binding to one). */
  embed?: DiscordEmbedPayload | null;
  /** Optional plain message content that accompanies the embed. */
  content?: string;
  /** True while the bound Embed Draft is still being fetched. */
  embedLoading?: boolean;
  /** True when the bound Embed Draft id no longer resolves to a draft. */
  embedMissing?: boolean;
};

function EmojiGlyph({ value }: { value?: string }) {
  const preview = emojiPreviewSrc(value);
  if (preview.type === "unicode") {
    return <span aria-hidden>{preview.text}</span>;
  }
  if (preview.type === "image") {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={preview.url} alt="" width={16} height={16} />
    );
  }
  return null;
}

export function RoleAssignmentPreview({
  menu,
  embed,
  content,
  embedLoading,
  embedMissing,
}: RoleAssignmentPreviewProps) {
  const interaction = (menu.interaction ??
    "buttons") as RoleMenuInteraction;
  const isEmbedBound = menu.binding_type === "embed_message";

  return (
    <div className="norgoth-role-assignment-preview border rounded p-3">
      <div className="small text-uppercase fw-semibold text-body-secondary mb-2">
        Member preview · {ROLE_MENU_INTERACTION_LABELS[interaction]}
      </div>

      {isEmbedBound ? (
        embedLoading ? (
          <div className="d-flex align-items-center gap-2 text-body-secondary small py-4">
            <CSpinner size="sm" /> Loading embed draft…
          </div>
        ) : embedMissing ? (
          <div className="border rounded p-3 small text-warning mb-2">
            <div className="fw-semibold">Embed Draft Missing</div>
            <div className="text-body-secondary">
              The bound Embed Message no longer exists. Re-select an Embed
              Message to restore the preview.
            </div>
          </div>
        ) : (
          <div className="mb-2">
            <MessagePreview content={content} embed={embed} mode="embed" showContentWithEmbed />
          </div>
        )
      ) : (
        <div
          className="rounded p-3 mb-2"
          style={{ background: "#313338", color: "#dbdee1" }}
        >
          <div className="fw-semibold text-white mb-1">
            {menu.title || "Untitled menu"}
          </div>
          <div className="small" style={{ color: "#b5bac1" }}>
            {menu.description || "Choose a role from the controls below."}
          </div>
        </div>
      )}

      <div
        className="rounded p-3"
        style={{ background: "#313338", color: "#dbdee1" }}
      >
        <div
          className="small text-uppercase fw-semibold mb-2"
          style={{ color: "#949ba4" }}
        >
          Role controls
        </div>

        {interaction === "select" ? (
          <div
            className="rounded px-3 py-2 d-flex align-items-center justify-content-between"
            style={{ background: "#1e1f22", border: "1px solid #3f4147" }}
          >
            <span className="small" style={{ color: "#949ba4" }}>
              Choose a role…
            </span>
            <span aria-hidden>▾</span>
          </div>
        ) : null}

        {interaction === "select" && menu.roles.length > 0 ? (
          <div
            className="mt-2 rounded overflow-hidden"
            style={{ background: "#2b2d31", border: "1px solid #3f4147" }}
          >
            {menu.roles.map((entry) => (
              <div
                key={entry.role_id}
                className="px-3 py-2 d-flex align-items-center gap-2 small"
                style={{ borderTop: "1px solid #3f4147" }}
              >
                <EmojiGlyph value={entry.emoji} />
                <span>{entry.label || "Option"}</span>
              </div>
            ))}
          </div>
        ) : null}

        {interaction === "buttons" ? (
          <div className="d-flex flex-wrap gap-2">
            {menu.roles.length === 0 ? (
              <span className="small" style={{ color: "#949ba4" }}>
                Add roles to preview buttons.
              </span>
            ) : (
              menu.roles.map((entry) => {
                const style = (entry.style ??
                  "secondary") as RoleMenuStyle;
                const swatch = ROLE_MENU_STYLE_SWATCHES[style];
                return (
                  <span
                    key={entry.role_id}
                    className="d-inline-flex align-items-center gap-1 px-3 py-1 rounded"
                    style={{
                      background: swatch.background,
                      color: swatch.color,
                      fontSize: "0.85rem",
                      fontWeight: 600,
                    }}
                  >
                    <EmojiGlyph value={entry.emoji} />
                    {entry.label || "Button"}
                  </span>
                );
              })
            )}
          </div>
        ) : null}

        {interaction === "reactions" ? (
          <div className="d-flex flex-wrap gap-2 align-items-center">
            {menu.roles.length === 0 ? (
              <span className="small" style={{ color: "#949ba4" }}>
                Add roles and emoji to preview reactions.
              </span>
            ) : (
              menu.roles.map((entry) => (
                <span
                  key={entry.role_id}
                  className="d-inline-flex align-items-center gap-1 px-2 py-1 rounded"
                  style={{ background: "#2b2d31", border: "1px solid #3f4147" }}
                  title={entry.label}
                >
                  <EmojiGlyph value={entry.emoji} />
                  <span className="small" style={{ color: "#949ba4" }}>
                    0
                  </span>
                </span>
              ))
            )}
          </div>
        ) : null}
      </div>
      <p className="mb-0 mt-2 small text-body-secondary">
        Preview only — shows what members will roughly see in Discord.
      </p>
    </div>
  );
}
