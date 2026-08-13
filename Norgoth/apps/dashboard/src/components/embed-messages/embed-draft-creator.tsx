"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CAlert, CFormInput, CFormLabel } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmbedEditor } from "@/components/discord/embed-editor";
import { MessagePreview } from "@/components/discord/message-preview";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import type { GuildChannel } from "@/stores/guild-store";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";
import {
  DISCORD_LIMITS,
  scrubEmptyEmbedUrls,
  validateEmbed,
} from "@/lib/discord/message-payload";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

const EMPTY_EMBED: DiscordEmbedPayload = {
  title: "",
  description: "",
  color: "#5865f2",
};

/** Live values authored in the creator, emitted via `onDraftChange`. */
export type EmbedDraftValue = {
  name: string;
  description: string;
  content: string;
  embed: DiscordEmbedPayload;
};

export type EmbedDraftCreatorProps = {
  guildId: string | null | undefined;
  /** Retained for host compatibility; the content-only editor does not use it. */
  channels?: GuildChannel[];
  mode?: "create" | "edit";
  /** Required when `mode === "edit"`. */
  messageId?: string;
  /** Prefills the form when editing. */
  initialMessage?: EmbedMessage | null;
  /** Fired after a successful create with the persisted draft. */
  onCreated?: (created: EmbedMessage) => void;
  /** Fired after a successful edit save with the updated draft. */
  onSaved?: (saved: EmbedMessage) => void;
  /** Optional secondary action (e.g. Back to list / Cancel). */
  onCancel?: () => void;
  cancelLabel?: string;
  /** Side-by-side preview+editor for modals / embedded hosts (preview left). */
  compact?: boolean;
  /**
   * Primary create-button label. Defaults to "Save Draft" for create mode and
   * "Save" for edit mode.
   */
  createLabel?: string;
  /** Hide the built-in message preview (host renders its own preview). */
  hidePreview?: boolean;
  /**
   * Hide the built-in Create/Save + Cancel actions. Use when the host persists
   * the draft itself (e.g. Self-Assignable Roles saves on "Save Menu").
   */
  hideActions?: boolean;
  /**
   * Controlled-authoring hook: fired on mount and whenever any field changes so
   * a host can render a live preview and persist the draft on demand.
   */
  onDraftChange?: (draft: EmbedDraftValue) => void;
};

/**
 * Host-agnostic Embed Draft authoring form. Owns only the reusable embed
 * CONTENT (name/description/content/embed), reuses the shared
 * `EmbedEditor`/`MessagePreview`, and persists through the central Embed Library
 * store (`create`/`update`). Deployment destination is owned by the consuming
 * feature (Deploy action, Self-Assignable Roles, Welcome/Leave, …), never by the
 * draft. It does NOT navigate — hosts react via `onCreated`/`onSaved`/`onCancel`.
 */
export function EmbedDraftCreator({
  guildId,
  mode = "create",
  messageId,
  initialMessage = null,
  onCreated,
  onSaved,
  onCancel,
  cancelLabel,
  compact = false,
  hidePreview = false,
  hideActions = false,
  onDraftChange,
  createLabel,
}: EmbedDraftCreatorProps) {
  const dict = useLocaleDict();
  const d = dict.embedLibraryPage;
  const create = useEmbedMessagesStore((s) => s.create);
  const update = useEmbedMessagesStore((s) => s.update);

  const isEdit = mode === "edit";
  const showPreviewColumn = !hidePreview;

  const [, setMessage] = useState<EmbedMessage | null>(initialMessage);
  const [name, setName] = useState(initialMessage?.name ?? "");
  const [description, setDescription] = useState(
    initialMessage?.description ?? ""
  );
  const [content, setContent] = useState(initialMessage?.content ?? "");
  const [embed, setEmbed] = useState<DiscordEmbedPayload>(
    initialMessage?.embed_json ?? EMPTY_EMBED
  );

  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState(false);

  const embedErrors = useMemo(() => validateEmbed(embed), [embed]);

  // Emit live values so a controlled host can render its own preview / persist
  // on demand. Kept in a ref so an inline callback does not retrigger the emit
  // effect (which would loop if the host updates state on each change).
  const onDraftChangeRef = useRef(onDraftChange);
  useEffect(() => {
    onDraftChangeRef.current = onDraftChange;
  }, [onDraftChange]);
  useEffect(() => {
    onDraftChangeRef.current?.({
      name,
      description,
      content,
      embed,
    });
  }, [name, description, content, embed]);

  async function handleSave(): Promise<void> {
    if (!guildId) return;
    if (!name.trim()) {
      setFeedback(d.nameRequired);
      setFeedbackError(true);
      return;
    }
    if (embedErrors.length > 0) {
      setFeedback(embedErrors[0]);
      setFeedbackError(true);
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const input = {
        name: name.trim(),
        description: description.trim(),
        content,
        embed_json: scrubEmptyEmbedUrls(embed),
      };
      const result =
        isEdit && messageId
          ? await update(guildId, messageId, input)
          : await create(guildId, input);

      if (!result) {
        const storeError = useEmbedMessagesStore.getState().error;
        setFeedback(storeError ?? d.failedToSave);
        setFeedbackError(true);
        return;
      }

      setMessage(result);
      setFeedback(d.saved);
      setFeedbackError(false);
      if (isEdit) onSaved?.(result);
      else onCreated?.(result);
    } finally {
      setSaving(false);
    }
  }

  const formCard = (
    <Card>
      <div className="d-flex flex-column gap-3">
        <div>
          <CFormLabel>{d.draftName}</CFormLabel>
          <CFormInput
            value={name}
            maxLength={120}
            onChange={(e) => setName(e.target.value)}
            placeholder={d.draftNamePlaceholder}
          />
        </div>
        <div>
          <CFormLabel>{d.description}</CFormLabel>
          <CFormInput
            value={description}
            maxLength={500}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={d.descriptionPlaceholder}
          />
        </div>
        <div>
          <CFormLabel>{d.messageContent}</CFormLabel>
          <RichMessageEditor
            value={content}
            onChange={setContent}
            height={140}
            placeholder={d.messageContentPlaceholder}
          />
          {content.length > DISCORD_LIMITS.content ? (
            <p className="small text-danger mb-0 mt-1">
              {formatDict(d.contentTooLong, { limit: DISCORD_LIMITS.content })}
            </p>
          ) : null}
        </div>

        <hr className="my-1" />

        <EmbedEditor
          value={embed}
          guildId={guildId ?? undefined}
          onChange={setEmbed}
          hideDescription
        />

        <div>
          <CFormLabel>{d.embedDescription}</CFormLabel>
          <RichMessageEditor
            value={embed.description ?? ""}
            onChange={(markdown) =>
              setEmbed((current) => ({ ...current, description: markdown }))
            }
            height={200}
            placeholder={d.embedDescriptionPlaceholder}
          />
        </div>

        {embedErrors.length > 0 ? (
          <CAlert color="warning" className="mb-0">
            {embedErrors.map((err) => (
              <div key={err}>{err}</div>
            ))}
          </CAlert>
        ) : null}

        {hideActions ? null : (
          <div className="d-flex gap-2">
            <Button
              variant="primary"
              onClick={() => void handleSave()}
              disabled={saving || !guildId}
            >
              {saving
                ? d.saving
                : isEdit
                  ? d.save
                  : (createLabel ?? d.saveDraft)}
            </Button>
            {onCancel ? (
              <Button variant="secondary" onClick={onCancel}>
                {cancelLabel ?? (isEdit ? d.backToList : d.cancel)}
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </Card>
  );

  const previewColumn = hidePreview ? null : (
    <div className="norgoth-embed-creator-preview d-flex flex-column gap-3">
      <MessagePreview
        content={content}
        embed={embed}
        mode="embed"
        showContentWithEmbed
        showImagePlaceholders
      />
    </div>
  );

  const editorColClass = showPreviewColumn
    ? "col-12 col-lg-7 norgoth-embed-creator-editor"
    : "col-12";
  const previewColClass = "col-12 col-lg-5";

  const layoutClass = compact
    ? "d-flex flex-column gap-3 norgoth-embed-draft-creator norgoth-embed-draft-creator-compact"
    : "d-flex flex-column gap-3 norgoth-embed-draft-creator";

  return (
    <div className={layoutClass}>
      {feedback ? (
        <CAlert color={feedbackError ? "danger" : "success"} className="mb-0">
          {feedback}
        </CAlert>
      ) : null}

      <div className="row g-4 align-items-start">
        {showPreviewColumn ? (
          <div className={previewColClass}>{previewColumn}</div>
        ) : null}
        <div className={editorColClass}>{formCard}</div>
      </div>
    </div>
  );
}
