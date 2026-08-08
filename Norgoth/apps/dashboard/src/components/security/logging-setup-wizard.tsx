"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CAlert,
  CFormCheck,
  CFormInput,
  CFormLabel,
  CFormSelect,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Stepper } from "@/components/ui/stepper";
import { EmbedColorPicker } from "@/components/discord/embed-color-picker";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import type { GuildChannel } from "@/stores/guild-store";
import { colorToHex, hexToColor, sanitizeChannelName } from "@/lib/logging";
import {
  useLoggingConfigStore,
  type LoggingCatalog,
  type LoggingConfigBody,
} from "@/stores/logging-config-store";

type GroupDraft = {
  key: string;
  label: string;
  included: boolean;
  mode: "new" | "existing";
  newEmoji: string;
  newName: string;
  channelId: string | null;
  defaultColorHex: string;
  events: {
    event_type: string;
    label: string;
    enabled: boolean;
    overrideColor: boolean;
    colorHex: string;
  }[];
};

const STEPS = [
  { id: "category", label: "Category" },
  { id: "channels", label: "Channels" },
  { id: "events", label: "Events & Colors" },
  { id: "review", label: "Review" },
];

function buildDraft(catalog: LoggingCatalog): GroupDraft[] {
  return catalog.groups.map((group) => {
    const defaultHex = colorToHex(group.default_color);
    return {
      key: group.key,
      label: group.label,
      included: group.key !== "voice",
      mode: "new" as const,
      newEmoji: "",
      newName: `${group.key}-log`,
      channelId: null,
      defaultColorHex: defaultHex,
      events: group.events.map((event) => ({
        event_type: event.event_type,
        label: event.label,
        enabled: true,
        overrideColor: false,
        colorHex: defaultHex,
      })),
    };
  });
}

/**
 * Compose the final Discord channel name from an optional (unicode) emoji icon
 * and the user-provided name. The text part is sanitised to Discord's rules;
 * the emoji is preserved and prefixed (Discord turns the space into a hyphen).
 */
function composeChannelName(emoji: string, name: string): string {
  const base = sanitizeChannelName(name);
  return emoji ? `${emoji} ${base}` : base;
}

type Props = {
  guildId: string;
  channels: GuildChannel[];
  onComplete: () => void;
};

export function LoggingSetupWizard({ guildId, channels, onComplete }: Props) {
  const catalog = useLoggingConfigStore((s) => s.catalog);
  const save = useLoggingConfigStore((s) => s.save);
  const provision = useLoggingConfigStore((s) => s.provision);
  const busy = useLoggingConfigStore((s) => s.busy);
  const error = useLoggingConfigStore((s) => s.error);

  const [step, setStep] = useState(0);
  const [categoryManaged, setCategoryManaged] = useState(true);
  const [categoryEmoji, setCategoryEmoji] = useState("");
  const [categoryName, setCategoryName] = useState("Norgoth Logs");
  const [groups, setGroups] = useState<GroupDraft[]>(() =>
    catalog ? buildDraft(catalog) : []
  );
  const [localError, setLocalError] = useState<string | null>(null);

  const includedGroups = useMemo(
    () => groups.filter((group) => group.included),
    [groups]
  );

  // Catalog can arrive after mount; initialise the draft once it's available.
  useEffect(() => {
    if (catalog && groups.length === 0) {
      setGroups(buildDraft(catalog));
    }
  }, [catalog, groups.length]);

  if (!catalog) {
    return (
      <Card>
        <p className="mb-0 text-body-secondary">Loading event catalog…</p>
      </Card>
    );
  }

  function patchGroup(key: string, patch: Partial<GroupDraft>) {
    setGroups((current) =>
      current.map((group) =>
        group.key === key ? { ...group, ...patch } : group
      )
    );
  }

  function patchEvent(
    groupKey: string,
    eventType: string,
    patch: Partial<GroupDraft["events"][number]>
  ) {
    setGroups((current) =>
      current.map((group) =>
        group.key === groupKey
          ? {
              ...group,
              events: group.events.map((event) =>
                event.event_type === eventType
                  ? { ...event, ...patch }
                  : event
              ),
            }
          : group
      )
    );
  }

  function validate(): string | null {
    if (includedGroups.length === 0) {
      return "Select at least one log group.";
    }
    for (const group of includedGroups) {
      if (group.mode === "existing" && !group.channelId) {
        return `Choose an existing channel for “${group.label}” or switch it to a new channel.`;
      }
      if (group.mode === "new" && !group.newName.trim()) {
        return `Give the “${group.label}” channel a name.`;
      }
    }
    return null;
  }

  async function handleCreate() {
    const validationError = validate();
    if (validationError) {
      setLocalError(validationError);
      return;
    }
    setLocalError(null);

    const body: LoggingConfigBody = {
      enabled: true,
      category_id: null,
      category_name: categoryManaged
        ? `${categoryEmoji ? `${categoryEmoji} ` : ""}${categoryName}`.trim()
        : null,
      norgoth_managed_category: categoryManaged,
      channels: includedGroups.map((group, index) => ({
        key: group.key,
        name:
          group.mode === "new"
            ? composeChannelName(group.newEmoji, group.newName)
            : channels.find((c) => c.id === group.channelId)?.name ??
              group.key,
        channel_id: group.mode === "existing" ? group.channelId : null,
        norgoth_managed: group.mode === "new",
        default_color: hexToColor(group.defaultColorHex),
        position: index,
      })),
      events: includedGroups.flatMap((group) =>
        group.events.map((event) => ({
          event_type: event.event_type,
          channel_key: group.key,
          color: event.overrideColor ? hexToColor(event.colorHex) : null,
          enabled: event.enabled,
        }))
      ),
    };

    const saved = await save(guildId, body);
    if (!saved) return;

    const needsProvision =
      categoryManaged || includedGroups.some((group) => group.mode === "new");
    if (needsProvision) {
      const provisioned = await provision(guildId);
      if (!provisioned) return;
    }
    onComplete();
  }

  return (
    <Card>
      <div className="d-flex flex-column gap-4">
        <div>
          <h2 className="h5 mb-1 fw-semibold">Logging Setup</h2>
          <p className="mb-0 small text-body-secondary">
            Provision log channels and route events in a few steps.
          </p>
        </div>

        <Stepper steps={STEPS} current={step} onStepClick={setStep} />

        {localError || error ? (
          <CAlert color="danger" className="mb-0 py-2">
            {localError ?? error}
          </CAlert>
        ) : null}

        {step === 0 ? (
          <div className="d-flex flex-column gap-3">
            <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
              <div>
                <div className="fw-medium">Create a Norgoth-managed category</div>
                <p className="mb-0 mt-1 small text-body-secondary">
                  Groups new log channels under a dedicated category that
                  Norgoth can manage and repair.
                </p>
              </div>
              <Switch
                checked={categoryManaged}
                onChange={setCategoryManaged}
                aria-label="Create managed category"
              />
            </div>
            {categoryManaged ? (
              <div className="d-flex align-items-end gap-2">
                <div>
                  <CFormLabel>Category icon (optional)</CFormLabel>
                  <DiscordEmojiPicker
                    value={categoryEmoji}
                    onChange={setCategoryEmoji}
                    placeholder="Icon"
                  />
                </div>
                <div className="flex-grow-1">
                  <CFormLabel>Category name</CFormLabel>
                  <CFormInput
                    value={categoryName}
                    maxLength={90}
                    onChange={(e) => setCategoryName(e.target.value)}
                  />
                </div>
              </div>
            ) : (
              <CAlert color="secondary" className="mb-0 py-2 small">
                New channels will be created at the top level. Existing channels
                keep their current location.
              </CAlert>
            )}
          </div>
        ) : null}

        {step === 1 ? (
          <div className="d-flex flex-column gap-3">
            {groups.map((group) => (
              <div key={group.key} className="border rounded p-3 d-flex flex-column gap-2">
                <div className="d-flex align-items-center justify-content-between gap-3">
                  <CFormCheck
                    id={`group-${group.key}`}
                    label={group.label}
                    checked={group.included}
                    onChange={(e) =>
                      patchGroup(group.key, { included: e.target.checked })
                    }
                  />
                  {group.included ? (
                    <div className="btn-group btn-group-sm" role="group">
                      <Button
                        variant={group.mode === "new" ? "primary" : "secondary"}
                        size="sm"
                        onClick={() => patchGroup(group.key, { mode: "new" })}
                      >
                        New channel
                      </Button>
                      <Button
                        variant={
                          group.mode === "existing" ? "primary" : "secondary"
                        }
                        size="sm"
                        onClick={() =>
                          patchGroup(group.key, { mode: "existing" })
                        }
                      >
                        Existing
                      </Button>
                    </div>
                  ) : null}
                </div>
                {group.included ? (
                  group.mode === "new" ? (
                    <div className="d-flex align-items-end gap-2">
                      <div>
                        <CFormLabel className="small">
                          Icon (optional)
                        </CFormLabel>
                        <DiscordEmojiPicker
                          value={group.newEmoji}
                          onChange={(value) =>
                            patchGroup(group.key, { newEmoji: value })
                          }
                          placeholder="Icon"
                        />
                      </div>
                      <div className="flex-grow-1">
                        <CFormLabel className="small">Channel name</CFormLabel>
                        <CFormInput
                          value={group.newName}
                          onChange={(e) =>
                            patchGroup(group.key, { newName: e.target.value })
                          }
                          onBlur={(e) =>
                            patchGroup(group.key, {
                              newName: sanitizeChannelName(e.target.value),
                            })
                          }
                        />
                      </div>
                    </div>
                  ) : (
                    <CFormSelect
                      value={group.channelId ?? ""}
                      onChange={(e) =>
                        patchGroup(group.key, {
                          channelId: e.target.value || null,
                        })
                      }
                    >
                      <option value="">Select a channel…</option>
                      {channels.map((channel) => (
                        <option key={channel.id} value={channel.id}>
                          #{channel.name}
                        </option>
                      ))}
                    </CFormSelect>
                  )
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {step === 2 ? (
          <div className="d-flex flex-column gap-3">
            {includedGroups.length === 0 ? (
              <CAlert color="secondary" className="mb-0">
                No groups selected. Go back and pick at least one.
              </CAlert>
            ) : (
              includedGroups.map((group) => (
                <div key={group.key} className="border rounded p-3 d-flex flex-column gap-2">
                  <div className="d-flex align-items-center justify-content-between gap-2">
                    <span className="fw-semibold">{group.label}</span>
                    <div className="d-flex align-items-center gap-2">
                      <span className="small text-body-secondary">
                        Group color
                      </span>
                      <EmbedColorPicker
                        value={group.defaultColorHex}
                        onChange={(hex) =>
                          patchGroup(group.key, { defaultColorHex: hex })
                        }
                        label="Group color"
                      />
                    </div>
                  </div>
                  <div className="d-flex flex-column gap-2">
                    {group.events.map((event) => (
                      <div
                        key={event.event_type}
                        className="d-flex flex-wrap align-items-center justify-content-between gap-2 border-top pt-2"
                      >
                        <CFormCheck
                          id={`evt-${event.event_type}`}
                          label={event.label}
                          checked={event.enabled}
                          onChange={(e) =>
                            patchEvent(group.key, event.event_type, {
                              enabled: e.target.checked,
                            })
                          }
                        />
                        <div className="d-flex align-items-center gap-2">
                          <CFormCheck
                            id={`ovr-${event.event_type}`}
                            label="Custom color"
                            checked={event.overrideColor}
                            onChange={(e) =>
                              patchEvent(group.key, event.event_type, {
                                overrideColor: e.target.checked,
                              })
                            }
                          />
                          {event.overrideColor ? (
                            <EmbedColorPicker
                              value={event.colorHex}
                              onChange={(hex) =>
                                patchEvent(group.key, event.event_type, {
                                  colorHex: hex,
                                })
                              }
                              label="Event color"
                            />
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="d-flex flex-column gap-3">
            <div className="border rounded p-3">
              <div className="fw-semibold mb-1">Category</div>
              <div className="small text-body-secondary">
                {categoryManaged
                  ? `Norgoth will create “${categoryEmoji ? `${categoryEmoji} ` : ""}${categoryName}”.`
                  : "No managed category."}
              </div>
            </div>
            <div className="border rounded p-3 d-flex flex-column gap-2">
              <div className="fw-semibold">Channels &amp; events</div>
              {includedGroups.map((group) => {
                const enabledEvents = group.events.filter((e) => e.enabled)
                  .length;
                return (
                  <div
                    key={group.key}
                    className="d-flex align-items-center justify-content-between gap-2 small"
                  >
                    <span>
                      <Badge variant="neutral">{group.label}</Badge>{" "}
                      {group.mode === "new"
                        ? `#${composeChannelName(group.newEmoji, group.newName)} (new)`
                        : `#${channels.find((c) => c.id === group.channelId)?.name ?? "?"}`}
                    </span>
                    <span className="text-body-secondary">
                      {enabledEvents} event{enabledEvents === 1 ? "" : "s"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

        <div className="d-flex align-items-center justify-content-between gap-2">
          <Button
            variant="secondary"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0 || busy}
          >
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button
              variant="primary"
              onClick={() => {
                if (step === 1) {
                  const validationError = validate();
                  if (validationError) {
                    setLocalError(validationError);
                    return;
                  }
                }
                setLocalError(null);
                setStep((s) => Math.min(STEPS.length - 1, s + 1));
              }}
            >
              Next
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => void handleCreate()}
              disabled={busy}
            >
              {busy ? "Creating…" : "Create logging"}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
