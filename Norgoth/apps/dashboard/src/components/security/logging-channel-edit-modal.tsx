"use client";

import { useMemo, useState } from "react";
import { CFormCheck, CFormInput, CFormLabel } from "@coreui/react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import { EmbedColorPicker } from "@/components/discord/embed-color-picker";
import {
  colorToHex,
  composeChannelName,
  hexToColor,
  sanitizeChannelName,
  splitEmojiName,
} from "@/lib/logging";
import {
  useLoggingConfigStore,
  type LoggingCatalog,
  type LoggingChannelConfig,
  type LoggingEventConfig,
} from "@/stores/logging-config-store";

type Props = {
  visible: boolean;
  guildId: string;
  channel: LoggingChannelConfig;
  catalog: LoggingCatalog | null;
  events: LoggingEventConfig[];
  onClose: () => void;
  onSaved: () => void;
};

type EventDraft = {
  assigned: boolean;
  override: boolean;
  colorHex: string;
};

export function LoggingChannelEditModal({
  visible,
  guildId,
  channel,
  catalog,
  events,
  onClose,
  onSaved,
}: Props) {
  const busy = useLoggingConfigStore((s) => s.busy);
  const error = useLoggingConfigStore((s) => s.error);
  const updateChannel = useLoggingConfigStore((s) => s.updateChannel);

  const initialName = splitEmojiName(channel.name);
  const [emoji, setEmoji] = useState(initialName.emoji);
  const [name, setName] = useState(initialName.name);
  const [colorHex, setColorHex] = useState(colorToHex(channel.default_color));

  // Events currently routed to this channel, keyed by event_type.
  const assignedByType = useMemo(() => {
    const map = new Map<string, LoggingEventConfig>();
    for (const event of events) {
      if (event.channel_key === channel.key) map.set(event.event_type, event);
    }
    return map;
  }, [events, channel.key]);

  const [drafts, setDrafts] = useState<Record<string, EventDraft>>(() => {
    const initial: Record<string, EventDraft> = {};
    for (const group of catalog?.groups ?? []) {
      for (const def of group.events) {
        const existing = assignedByType.get(def.event_type);
        initial[def.event_type] = {
          assigned: Boolean(existing?.enabled),
          override: existing?.color != null,
          colorHex: colorToHex(existing?.color ?? group.default_color),
        };
      }
    }
    return initial;
  });

  function patchDraft(eventType: string, patch: Partial<EventDraft>) {
    setDrafts((prev) => ({
      ...prev,
      [eventType]: { ...prev[eventType], ...patch },
    }));
  }

  async function handleSave() {
    const channelEvents: LoggingEventConfig[] = [];
    for (const group of catalog?.groups ?? []) {
      for (const def of group.events) {
        const draft = drafts[def.event_type];
        if (!draft?.assigned) continue;
        channelEvents.push({
          event_type: def.event_type,
          channel_key: channel.key,
          color: draft.override ? hexToColor(draft.colorHex) : null,
          enabled: true,
        });
      }
    }

    const saved = await updateChannel(
      guildId,
      channel.key,
      {
        name: composeChannelName(emoji, name),
        default_color: hexToColor(colorHex),
      },
      channelEvents
    );
    if (saved) onSaved();
  }

  return (
    <FeatureConfigurationModal
      visible={visible}
      title="Edit logging channel"
      description="Update this channel's name, colour, and which events route to it. Other channels are unaffected."
      category="security"
      icon="cilList"
      size="xl"
      onClose={onClose}
      onSave={handleSave}
      saving={busy}
      error={error}
      saveLabel="Save channel"
    >
      <div className="d-flex flex-column gap-4">
        <div className="d-flex flex-wrap align-items-end gap-3">
          <div>
            <CFormLabel className="small">Icon (optional)</CFormLabel>
            <DiscordEmojiPicker
              value={emoji}
              onChange={setEmoji}
              placeholder="Icon"
            />
          </div>
          <div className="flex-grow-1" style={{ minWidth: 200 }}>
            <CFormLabel className="small">Channel name</CFormLabel>
            <CFormInput
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={(e) => setName(sanitizeChannelName(e.target.value))}
            />
          </div>
          <div>
            <CFormLabel className="small">Default colour</CFormLabel>
            <EmbedColorPicker value={colorHex} onChange={setColorHex} />
          </div>
        </div>

        <div className="d-flex flex-column gap-3">
          {(catalog?.groups ?? []).map((group) => (
            <div key={group.key} className="border rounded p-3">
              <div className="d-flex align-items-center justify-content-between mb-2">
                <span className="fw-semibold small text-uppercase text-body-secondary">
                  {group.label}
                </span>
              </div>
              <div className="d-flex flex-column gap-2">
                {group.events.map((def) => {
                  const draft = drafts[def.event_type];
                  if (!draft) return null;
                  return (
                    <div
                      key={def.event_type}
                      className="d-flex flex-wrap align-items-center gap-3"
                    >
                      <CFormCheck
                        id={`evt-${def.event_type}`}
                        label={def.label}
                        checked={draft.assigned}
                        onChange={(e) =>
                          patchDraft(def.event_type, {
                            assigned: e.target.checked,
                          })
                        }
                      />
                      {draft.assigned ? (
                        <div className="d-flex align-items-center gap-2 ms-auto">
                          <CFormCheck
                            id={`ovr-${def.event_type}`}
                            label="Custom colour"
                            checked={draft.override}
                            onChange={(e) =>
                              patchDraft(def.event_type, {
                                override: e.target.checked,
                              })
                            }
                          />
                          {draft.override ? (
                            <EmbedColorPicker
                              value={draft.colorHex}
                              onChange={(hex) =>
                                patchDraft(def.event_type, { colorHex: hex })
                              }
                            />
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </FeatureConfigurationModal>
  );
}
