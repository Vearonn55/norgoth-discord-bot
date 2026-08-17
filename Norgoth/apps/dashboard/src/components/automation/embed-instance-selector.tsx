"use client";

import { useEffect, useMemo, useState } from "react";
import { CFormLabel, CFormSelect } from "@coreui/react";
import { useLocaleDict } from "@/lib/locale-dict";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";

type EmbedInstanceSelectorProps = {
  guildId: string;
  channelNames: Map<string, string>;
  embedMessageId: string | null | undefined;
  channelId: string | null | undefined;
  onChange: (
    embedMessageId: string | null,
    embedDeliveryId: string | null,
    channelId: string | null
  ) => void;
};

export function EmbedInstanceSelector({
  guildId,
  channelNames,
  embedMessageId,
  channelId,
  onChange,
}: EmbedInstanceSelectorProps) {
  const dict = useLocaleDict();
  const d = dict.roleMenusPage;

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

  const channelOptions = useMemo(
    () => Array.from(channelNames.entries()),
    [channelNames]
  );

  return (
    <div className="d-flex flex-column gap-3">
      <div>
        <CFormLabel>{d.embedMessage}</CFormLabel>
        <input
          className="form-control mb-2"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={d.searchEmbedMessages}
        />
        <CFormSelect
          value={embedMessageId ?? ""}
          onChange={(event) => {
            const id = event.target.value || null;
            onChange(id, null, channelId ?? null);
          }}
        >
          <option value="">{d.selectEmbedMessage}</option>
          {filteredMessages.map((message) => (
            <option key={message.id} value={message.id}>
              {message.name}
              {message.has_published ? "" : d.draftSuffix}
            </option>
          ))}
        </CFormSelect>
        {loading ? (
          <p className="small text-body-secondary mt-1 mb-0">{d.loadingShort}</p>
        ) : null}
        <p className="small text-body-secondary mt-1 mb-0">{d.templateHelp}</p>
      </div>

      {selectedMessage ? (
        <div>
          <CFormLabel>{d.postToChannel}</CFormLabel>
          <CFormSelect
            value={channelId ?? ""}
            onChange={(event) => {
              onChange(
                selectedMessage.id,
                null,
                event.target.value || null
              );
            }}
          >
            <option value="">{d.selectChannel}</option>
            {channelId && !channelNames.has(channelId) ? (
              <option value={channelId} disabled>
                {dict.common.channelUnavailable}
              </option>
            ) : null}
            {channelOptions.map(([id, name]) => (
              <option key={id} value={id}>
                #{name}
              </option>
            ))}
          </CFormSelect>
        </div>
      ) : null}
    </div>
  );
}
