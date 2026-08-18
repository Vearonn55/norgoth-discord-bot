"use client";

import {
  CButton,
  CFormCheck,
  CFormInput,
  CFormLabel,
  CFormTextarea,
} from "@coreui/react";
import type { DiscordEmbedField, DiscordEmbedPayload } from "@/lib/discord/message-payload";
import { DISCORD_LIMITS } from "@/lib/discord/message-payload";
import { EmbedColorPicker } from "@/components/discord/embed-color-picker";
import { EmbedMediaPicker } from "@/components/discord/embed-media-picker";

type EmbedEditorProps = {
  value: DiscordEmbedPayload;
  onChange: (next: DiscordEmbedPayload) => void;
  /** Optional guild id enables local image uploads in the media pickers. */
  guildId?: string;
  /**
   * Hides the built-in description textarea. Use when the embed body is driven
   * by an external editor (e.g. the level-up TinyMCE message) so there is a
   * single source of truth for the description.
   */
  hideDescription?: boolean;
};

const emptyField = (): DiscordEmbedField => ({
  name: "",
  value: "",
  inline: false,
});

export function EmbedEditor({
  value,
  onChange,
  guildId,
  hideDescription = false,
}: EmbedEditorProps) {
  const fields = value.fields ?? [];
  const author = value.author ?? {};

  const patchAuthor = (patch: Partial<DiscordEmbedPayload["author"]>) => {
    const next = { ...author, ...patch };
    const hasAuthor = next.name || next.url || next.icon_url;
    onChange({ ...value, author: hasAuthor ? next : undefined });
  };

  return (
    <div className="d-flex flex-column gap-3 norgoth-embed-editor">
      <div className="row g-3 align-items-end">
        <div className="col-md-8">
          <CFormLabel>Embed title</CFormLabel>
          <CFormInput
            value={value.title ?? ""}
            maxLength={DISCORD_LIMITS.embedTitle}
            onChange={(e) => onChange({ ...value, title: e.target.value })}
          />
        </div>
        <div className="col-md-4">
          <CFormLabel className="d-block">Color</CFormLabel>
          <EmbedColorPicker
            value={value.color}
            onChange={(hex) => onChange({ ...value, color: hex })}
          />
        </div>
      </div>

      {hideDescription ? null : (
        <div>
          <CFormLabel>Embed description</CFormLabel>
          <CFormTextarea
            rows={4}
            value={value.description ?? ""}
            onChange={(e) => onChange({ ...value, description: e.target.value })}
          />
        </div>
      )}

      <div className="row g-3">
        <div className="col-md-6">
          <CFormLabel>Author name</CFormLabel>
          <CFormInput
            value={author.name ?? ""}
            maxLength={DISCORD_LIMITS.authorName}
            onChange={(e) => patchAuthor({ name: e.target.value })}
          />
        </div>
        <div className="col-md-6">
          <CFormLabel>Author icon URL</CFormLabel>
          <CFormInput
            value={author.icon_url ?? ""}
            placeholder="https://…"
            onChange={(e) => patchAuthor({ icon_url: e.target.value })}
          />
        </div>
      </div>

      <div className="row g-3">
        <div className="col-md-6">
          <CFormLabel>Footer</CFormLabel>
          <CFormInput
            value={value.footer ?? ""}
            maxLength={DISCORD_LIMITS.embedFooter}
            onChange={(e) => onChange({ ...value, footer: e.target.value })}
          />
        </div>
        <div className="col-md-6">
          <CFormLabel>Footer icon URL</CFormLabel>
          <CFormInput
            value={value.footer_icon_url ?? ""}
            placeholder="https://…"
            onChange={(e) =>
              onChange({ ...value, footer_icon_url: e.target.value })
            }
          />
        </div>
      </div>

      <div className="row g-3">
        <div className="col-md-6">
          <EmbedMediaPicker
            label="Thumbnail"
            helper="Shown in the upper-right of the embed."
            value={value.thumbnail_url ?? ""}
            guildId={guildId}
            onChange={(url) => onChange({ ...value, thumbnail_url: url })}
          />
        </div>
        <div className="col-md-6">
          <EmbedMediaPicker
            label="Main image / banner"
            helper="Shown as a large banner beneath the body."
            value={value.image_url ?? ""}
            guildId={guildId}
            onChange={(url) => onChange({ ...value, image_url: url })}
          />
        </div>
      </div>

      <div>
        <div className="d-flex align-items-center justify-content-between mb-2">
          <CFormLabel className="mb-0">
            Fields ({fields.length}/{DISCORD_LIMITS.embedFields})
          </CFormLabel>
          <CButton
            type="button"
            color="secondary"
            variant="outline"
            size="sm"
            disabled={fields.length >= DISCORD_LIMITS.embedFields}
            onClick={() =>
              onChange({ ...value, fields: [...fields, emptyField()] })
            }
          >
            Add field
          </CButton>
        </div>
        <div className="d-flex flex-column gap-2">
          {fields.map((field, index) => (
            <div key={index} className="border rounded p-3">
              <div className="row g-2 align-items-end">
                <div className="col-md-4">
                  <CFormLabel className="small">Name</CFormLabel>
                  <CFormInput
                    value={field.name}
                    maxLength={DISCORD_LIMITS.fieldName}
                    onChange={(e) => {
                      const next = [...fields];
                      next[index] = { ...field, name: e.target.value };
                      onChange({ ...value, fields: next });
                    }}
                  />
                </div>
                <div className="col-md-5">
                  <CFormLabel className="small">Value</CFormLabel>
                  <CFormInput
                    value={field.value}
                    maxLength={DISCORD_LIMITS.fieldValue}
                    onChange={(e) => {
                      const next = [...fields];
                      next[index] = { ...field, value: e.target.value };
                      onChange({ ...value, fields: next });
                    }}
                  />
                </div>
                <div className="col-md-2">
                  <CFormCheck
                    label="Inline"
                    checked={Boolean(field.inline)}
                    onChange={(e) => {
                      const next = [...fields];
                      next[index] = { ...field, inline: e.target.checked };
                      onChange({ ...value, fields: next });
                    }}
                  />
                </div>
                <div className="col-md-1">
                  <CButton
                    type="button"
                    color="danger"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      onChange({
                        ...value,
                        fields: fields.filter((_, i) => i !== index),
                      })
                    }
                  >
                    ×
                  </CButton>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
