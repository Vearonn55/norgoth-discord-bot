"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CAlert,
  CFormInput,
  CFormLabel,
  CFormTextarea,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GuildChannelMultiSelect } from "@/components/ui/guild-channel-multi-select";
import { EmbedEditor } from "@/components/discord/embed-editor";
import { MessagePreview } from "@/components/discord/message-preview";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useEmbedMessagesStore,
  type EmbedDeliveryStatus,
  type EmbedMessage,
} from "@/stores/embed-messages-store";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";
import { validateEmbed } from "@/lib/discord/message-payload";

const STATUS_LABELS: Record<EmbedDeliveryStatus, string> = {
  synced: "Synced",
  message_missing: "Message Missing",
  channel_missing: "Channel Missing",
  permission_missing: "Permission Missing",
  webhook_missing: "Webhook Missing",
  pending: "Pending",
  error: "Error",
};

const EMPTY_EMBED: DiscordEmbedPayload = {
  title: "",
  description: "",
  color: "#5865f2",
};

type Props = {
  lang: string;
  messageId: string;
};

export function EmbedMessageEditor({ lang, messageId }: Props) {
  const router = useRouter();
  const { guildId, resources } = useFirstGuild();
  const isNew = messageId === "new";

  const getMessage = useEmbedMessagesStore((s) => s.get);
  const create = useEmbedMessagesStore((s) => s.create);
  const update = useEmbedMessagesStore((s) => s.update);

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState(false);

  const [message, setMessage] = useState<EmbedMessage | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState("");
  const [embed, setEmbed] = useState<DiscordEmbedPayload>(EMPTY_EMBED);
  const [targetChannelIds, setTargetChannelIds] = useState<string[]>([]);

  useEffect(() => {
    if (isNew || !guildId) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    void getMessage(guildId, messageId).then((loaded) => {
      if (!active) return;
      if (loaded) {
        setMessage(loaded);
        setName(loaded.name);
        setDescription(loaded.description);
        setContent(loaded.content);
        setEmbed(loaded.embed_json ?? EMPTY_EMBED);
        setTargetChannelIds(loaded.target_channel_ids ?? []);
      }
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [guildId, isNew, messageId, getMessage]);

  const embedErrors = useMemo(() => validateEmbed(embed), [embed]);

  async function handleSave(): Promise<string | null> {
    if (!guildId) return null;
    if (!name.trim()) {
      setFeedback("Name is required.");
      setFeedbackError(true);
      return null;
    }
    if (embedErrors.length > 0) {
      setFeedback(embedErrors[0]);
      setFeedbackError(true);
      return null;
    }
    setSaving(true);
    setFeedback(null);
    try {
      const input = {
        name: name.trim(),
        description: description.trim(),
        content,
        embed_json: embed,
        target_channel_ids: targetChannelIds,
      };
      const result = isNew
        ? await create(guildId, input)
        : await update(guildId, messageId, input);
      if (!result) {
        const storeError = useEmbedMessagesStore.getState().error;
        setFeedback(storeError ?? "Failed to save.");
        setFeedbackError(true);
        return null;
      }
      setMessage(result);
      setFeedback("Saved.");
      setFeedbackError(false);
      if (isNew) {
        router.replace(`/${lang}/messages/embed-messages/${result.id}`);
      }
      return result.id;
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <CSpinner />
      </div>
    );
  }

  const channels = resources?.channels ?? [];
  const deliveries = message?.deliveries ?? [];

  return (
    <div className="d-flex flex-column gap-4">
      {feedback ? (
        <CAlert color={feedbackError ? "danger" : "success"} className="mb-0">
          {feedback}
        </CAlert>
      ) : null}

      <div className="row g-4">
        <div className="col-xl-7">
          <Card>
            <div className="d-flex flex-column gap-3">
              <div>
                <CFormLabel>Name</CFormLabel>
                <CFormInput
                  value={name}
                  maxLength={120}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Internal name (not shown in Discord)"
                />
              </div>
              <div>
                <CFormLabel>Description</CFormLabel>
                <CFormInput
                  value={description}
                  maxLength={500}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional note for your team"
                />
              </div>
              <div>
                <CFormLabel>Message content (above embed)</CFormLabel>
                <CFormTextarea
                  rows={2}
                  value={content}
                  maxLength={2000}
                  onChange={(e) => setContent(e.target.value)}
                />
              </div>

              <hr className="my-1" />

              <EmbedEditor
                value={embed}
                guildId={guildId ?? undefined}
                onChange={setEmbed}
              />

              {embedErrors.length > 0 ? (
                <CAlert color="warning" className="mb-0">
                  {embedErrors.map((err) => (
                    <div key={err}>{err}</div>
                  ))}
                </CAlert>
              ) : null}

              <div className="d-flex gap-2">
                <Button
                  variant="primary"
                  onClick={handleSave}
                  disabled={saving || !guildId}
                >
                  {saving ? "Saving…" : isNew ? "Create" : "Save"}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() =>
                    router.push(`/${lang}/messages/embed-messages`)
                  }
                >
                  Back to list
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <div className="col-xl-5">
          <div className="d-flex flex-column gap-4">
            <MessagePreview content={content} embed={embed} showEmbed />

            <Card>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h3 className="h6 mb-1">Publish targets</h3>
                  <p className="small text-body-secondary mb-0">
                    Choose the channels this embed publishes to. Saving stores
                    the targets — it does not post anything. Publish and Re-Sync
                    from the Embed Messages list.
                  </p>
                </div>
                <GuildChannelMultiSelect
                  channels={channels}
                  selectedIds={targetChannelIds}
                  onChange={setTargetChannelIds}
                  maxSelected={25}
                />

                {!isNew && deliveries.length > 0 ? (
                  <>
                    <hr className="my-1" />
                    <h3 className="h6 mb-0">
                      Sent messages ({deliveries.length})
                    </h3>
                    <div className="d-flex flex-column gap-2">
                      {deliveries.map((delivery) => {
                        const channelName = channels.find(
                          (c) => c.id === delivery.channel_id
                        )?.name;
                        return (
                          <div
                            key={delivery.id}
                            className="d-flex align-items-center justify-content-between border rounded px-2 py-1"
                          >
                            <span className="small text-truncate">
                              #{channelName ?? delivery.channel_id}
                            </span>
                            <Badge
                              variant={
                                delivery.status === "synced"
                                  ? "success"
                                  : delivery.status === "pending"
                                    ? "neutral"
                                    : "danger"
                              }
                            >
                              {STATUS_LABELS[delivery.status] ?? delivery.status}
                            </Badge>
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : null}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
