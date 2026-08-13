"use client";

import { useMemo, useState } from "react";
import { CFormCheck, CFormInput, CFormLabel } from "@coreui/react";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { Button } from "@/components/ui/button";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import { EmbedColorPicker } from "@/components/discord/embed-color-picker";
import {
  colorToHex,
  composeChannelName,
  hexToColor,
  sanitizeChannelName,
  splitEmojiName,
} from "@/lib/logging";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
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
  const dict = useLocaleDict();
  const d = dict.discordLogsPage;
  const busy = useLoggingConfigStore((s) => s.busy);
  const error = useLoggingConfigStore((s) => s.error);
  const updateChannel = useLoggingConfigStore((s) => s.updateChannel);
  const deleteDiscordChannel = useLoggingConfigStore(
    (s) => s.deleteDiscordChannel,
  );

  const categoryGroup = useMemo(
    () =>
      (catalog?.groups ?? []).find((group) => group.key === channel.key) ??
      null,
    [catalog, channel.key],
  );

  const categoryLabel = categoryGroup?.label ?? channel.key;
  const hasDiscordChannel = Boolean(channel.channel_id);

  const initialName = splitEmojiName(channel.name);
  const [emoji, setEmoji] = useState(initialName.emoji);
  const [name, setName] = useState(initialName.name);
  const [colorHex, setColorHex] = useState(colorToHex(channel.default_color));
  const [confirmDelete, setConfirmDelete] = useState(false);

  const assignedByType = useMemo(() => {
    const map = new Map<string, LoggingEventConfig>();
    for (const event of events) {
      if (event.channel_key === channel.key) map.set(event.event_type, event);
    }
    return map;
  }, [events, channel.key]);

  const [drafts, setDrafts] = useState<Record<string, EventDraft>>(() => {
    const initial: Record<string, EventDraft> = {};
    const group = (catalog?.groups ?? []).find((g) => g.key === channel.key);
    if (!group) return initial;
    for (const def of group.events) {
      const existing = assignedByType.get(def.event_type);
      initial[def.event_type] = {
        assigned: Boolean(existing?.enabled),
        override: existing?.color != null,
        colorHex: colorToHex(existing?.color ?? group.default_color),
      };
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
    if (!categoryGroup) return;
    const channelEvents: LoggingEventConfig[] = [];
    for (const def of categoryGroup.events) {
      const draft = drafts[def.event_type];
      if (!draft?.assigned) continue;
      channelEvents.push({
        event_type: def.event_type,
        channel_key: channel.key,
        color: draft.override ? hexToColor(draft.colorHex) : null,
        enabled: true,
      });
    }

    const saved = await updateChannel(
      guildId,
      channel.key,
      {
        name: composeChannelName(emoji, name),
        default_color: hexToColor(colorHex),
      },
      channelEvents,
    );
    if (saved) onSaved();
  }

  async function handleDeleteConfirm() {
    const saved = await deleteDiscordChannel(guildId, channel.key);
    if (saved) {
      setConfirmDelete(false);
      onSaved();
    }
  }

  return (
    <>
      <FeatureConfigurationModal
        visible={visible}
        title={formatDict(d.modalTitle, { label: categoryLabel })}
        description={formatDict(d.modalDescription, {
          label: categoryLabel.toLowerCase(),
        })}
        category="security"
        icon="cilList"
        size="lg"
        onClose={onClose}
        onSave={handleSave}
        saving={busy}
        error={error}
        saveLabel={d.save}
        footer={
          <>
            <Button variant="secondary" onClick={onClose} disabled={busy}>
              {d.cancel}
            </Button>
            {hasDiscordChannel ? (
              <Button
                variant="danger"
                onClick={() => setConfirmDelete(true)}
                disabled={busy}
                className="me-auto"
              >
                {d.deleteLogChannel}
              </Button>
            ) : null}
            <Button
              variant="primary"
              onClick={() => void handleSave()}
              disabled={busy || !categoryGroup}
            >
              {busy ? d.saving : d.save}
            </Button>
          </>
        }
      >
        <div className="d-flex flex-column gap-4">
          <div className="d-flex flex-wrap align-items-end gap-3">
            <div>
              <CFormLabel className="small">{d.iconOptional}</CFormLabel>
              <DiscordEmojiPicker
                value={emoji}
                onChange={setEmoji}
                placeholder={d.iconPlaceholder}
              />
            </div>
            <div className="flex-grow-1" style={{ minWidth: 200 }}>
              <CFormLabel className="small">{d.channelName}</CFormLabel>
              <CFormInput
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={(e) => setName(sanitizeChannelName(e.target.value))}
              />
            </div>
            <div>
              <CFormLabel className="small">{d.defaultColour}</CFormLabel>
              <EmbedColorPicker value={colorHex} onChange={setColorHex} />
            </div>
          </div>

          {categoryGroup ? (
            <div className="border rounded p-3 d-flex flex-column gap-2">
              <div className="fw-semibold small text-uppercase text-body-secondary">
                {formatDict(d.eventsHeading, { label: categoryGroup.label })}
              </div>
              {categoryGroup.events.map((def) => {
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
                          label={d.customColour}
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
          ) : (
            <p className="mb-0 small text-body-secondary">
              {d.noCatalogEvents}
            </p>
          )}
        </div>
      </FeatureConfigurationModal>

      <ConfirmDialog
        visible={confirmDelete}
        title={d.deleteChannelTitle}
        message={d.deleteChannelMessage}
        confirmLabel={d.deleteLogChannel}
        destructive
        busy={busy}
        onConfirm={() => {
          void handleDeleteConfirm();
        }}
        onCancel={() => setConfirmDelete(false)}
      />
    </>
  );
}
