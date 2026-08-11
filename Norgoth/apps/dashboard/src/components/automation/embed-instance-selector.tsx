"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CFormLabel, CFormSelect } from "@coreui/react";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/datetime";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
  type EmbedMessageDelivery,
} from "@/stores/embed-messages-store";

type EmbedInstanceSelectorProps = {
  guildId: string;
  channelNames: Map<string, string>;
  embedMessageId: string | null | undefined;
  embedDeliveryId: string | null | undefined;
  onChange: (
    embedMessageId: string | null,
    embedDeliveryId: string | null,
    channelId: string | null
  ) => void;
};

/** A published Embed Message delivery is selectable when it is live in Discord. */
function isSelectableInstance(delivery: EmbedMessageDelivery): boolean {
  return Boolean(delivery.discord_message_id);
}

export function EmbedInstanceSelector({
  guildId,
  channelNames,
  embedMessageId,
  embedDeliveryId,
  onChange,
}: EmbedInstanceSelectorProps) {
  const params = useParams();
  const lang = String(params?.lang || "en");

  const messages = useEmbedMessagesStore((s) => s.messages);
  const loading = useEmbedMessagesStore((s) => s.loading);
  const load = useEmbedMessagesStore((s) => s.load);

  const [search, setSearch] = useState("");

  useEffect(() => {
    if (guildId) void load(guildId);
  }, [guildId, load]);

  const selectedMessage: EmbedMessage | undefined = useMemo(
    () => messages.find((m) => m.id === embedMessageId),
    [messages, embedMessageId]
  );

  const filteredMessages = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return messages;
    return messages.filter((m) =>
      `${m.name} ${m.description}`.toLowerCase().includes(q)
    );
  }, [messages, search]);

  const instances = useMemo(
    () => (selectedMessage?.deliveries ?? []).filter(isSelectableInstance),
    [selectedMessage]
  );

  function instanceLabel(delivery: EmbedMessageDelivery): string {
    const channel = channelNames.get(delivery.channel_id) ?? delivery.channel_id;
    const when = formatDateTime(
      delivery.published_at ?? delivery.created_at,
      lang
    );
    return `#${channel} : ${when}`;
  }

  return (
    <div className="d-flex flex-column gap-3">
      <div>
        <CFormLabel>Embed Message</CFormLabel>
        <input
          className="form-control mb-2"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search embed messages…"
        />
        <CFormSelect
          value={embedMessageId ?? ""}
          onChange={(event) => {
            const id = event.target.value || null;
            onChange(id, null, null);
          }}
        >
          <option value="">Select an Embed Message…</option>
          {filteredMessages.map((message) => (
            <option key={message.id} value={message.id}>
              {message.name}
              {message.has_published ? "" : " (draft)"}
            </option>
          ))}
        </CFormSelect>
        {loading ? (
          <p className="small text-body-secondary mt-1 mb-0">Loading…</p>
        ) : null}
      </div>

      {selectedMessage ? (
        instances.length > 0 ? (
          <div>
            <CFormLabel>Published instance</CFormLabel>
            <CFormSelect
              value={embedDeliveryId ?? ""}
              onChange={(event) => {
                const deliveryId = event.target.value || null;
                const delivery = instances.find((d) => d.id === deliveryId);
                onChange(
                  selectedMessage.id,
                  deliveryId,
                  delivery ? delivery.channel_id : null
                );
              }}
            >
              <option value="">Select a published instance…</option>
              {instances.map((delivery) => (
                <option key={delivery.id} value={delivery.id}>
                  {instanceLabel(delivery)}
                </option>
              ))}
            </CFormSelect>
            <p className="small text-body-secondary mt-1 mb-0">
              Role controls attach to this exact published message. The embed
              content stays owned by the Embed Message.
            </p>
          </div>
        ) : (
          <div className="border rounded p-3 small d-flex flex-column gap-2">
            <span className="text-warning fw-medium">
              This Embed Message has no published instance yet.
            </span>
            <span className="text-body-secondary">
              Publish the Embed Message to a channel first, then select the
              instance here.
            </span>
            <Link
              href={`/${lang}/messages/embed-messages/${selectedMessage.id}`}
              className="text-decoration-none"
            >
              Open Embed Message →
            </Link>
          </div>
        )
      ) : null}

      {embedDeliveryId ? (
        <Badge variant="success">Instance bound</Badge>
      ) : null}
    </div>
  );
}
