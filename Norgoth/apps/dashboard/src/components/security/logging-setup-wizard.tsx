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
import {
  colorToHex,
  composeCategoryName,
  composeChannelName,
  hexToColor,
  sanitizeChannelName,
} from "@/lib/logging";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
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

type Props = {
  guildId: string;
  channels: GuildChannel[];
  onComplete: () => void;
};

export function LoggingSetupWizard({ guildId, channels, onComplete }: Props) {
  const dict = useLocaleDict();
  const d = dict.discordLogsPage;
  const catalog = useLoggingConfigStore((s) => s.catalog);
  const save = useLoggingConfigStore((s) => s.save);
  const provision = useLoggingConfigStore((s) => s.provision);
  const busy = useLoggingConfigStore((s) => s.busy);
  const error = useLoggingConfigStore((s) => s.error);

  const steps = useMemo(
    () => [
      { id: "category", label: d.stepCategory },
      { id: "channels", label: d.stepChannels },
      { id: "events", label: d.stepEvents },
      { id: "review", label: d.stepReview },
    ],
    [d.stepCategory, d.stepChannels, d.stepEvents, d.stepReview],
  );

  const [step, setStep] = useState(0);
  const [categoryManaged, setCategoryManaged] = useState(true);
  const [categoryEmoji, setCategoryEmoji] = useState("");
  const [categoryName, setCategoryName] = useState("NorBot Logs");
  const [groups, setGroups] = useState<GroupDraft[]>(() =>
    catalog ? buildDraft(catalog) : [],
  );
  const [localError, setLocalError] = useState<string | null>(null);

  const includedGroups = useMemo(
    () => groups.filter((group) => group.included),
    [groups],
  );

  useEffect(() => {
    if (catalog && groups.length === 0) {
      setGroups(buildDraft(catalog));
    }
  }, [catalog, groups.length]);

  if (!catalog) {
    return (
      <Card>
        <p className="mb-0 text-body-secondary">{d.loadingCatalog}</p>
      </Card>
    );
  }

  function patchGroup(key: string, patch: Partial<GroupDraft>) {
    setGroups((current) =>
      current.map((group) =>
        group.key === key ? { ...group, ...patch } : group,
      ),
    );
  }

  function patchEvent(
    groupKey: string,
    eventType: string,
    patch: Partial<GroupDraft["events"][number]>,
  ) {
    setGroups((current) =>
      current.map((group) =>
        group.key === groupKey
          ? {
              ...group,
              events: group.events.map((event) =>
                event.event_type === eventType
                  ? { ...event, ...patch }
                  : event,
              ),
            }
          : group,
      ),
    );
  }

  function validate(): string | null {
    if (includedGroups.length === 0) {
      return d.selectOneGroup;
    }
    for (const group of includedGroups) {
      if (group.mode === "existing" && !group.channelId) {
        return formatDict(d.chooseExistingChannel, { label: group.label });
      }
      if (group.mode === "new" && !group.newName.trim()) {
        return formatDict(d.giveChannelName, { label: group.label });
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
        ? composeCategoryName(categoryEmoji, categoryName)
        : null,
      norgoth_managed_category: categoryManaged,
      channels: includedGroups.map((group, index) => ({
        key: group.key,
        name:
          group.mode === "new"
            ? composeChannelName(group.newEmoji, group.newName)
            : (channels.find((c) => c.id === group.channelId)?.name ??
              group.key),
        channel_id: group.mode === "existing" ? group.channelId : null,
        norgoth_managed: group.mode === "new",
        default_color: hexToColor(group.defaultColorHex),
        position: index,
        enabled: true,
      })),
      events: includedGroups.flatMap((group) =>
        group.events.map((event) => ({
          event_type: event.event_type,
          channel_key: group.key,
          color: event.overrideColor ? hexToColor(event.colorHex) : null,
          enabled: event.enabled,
        })),
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
          <h2 className="h5 mb-1 fw-semibold">{d.wizardTitle}</h2>
          <p className="mb-0 small text-body-secondary">{d.wizardDescription}</p>
        </div>

        <Stepper steps={steps} current={step} onStepClick={setStep} />

        {localError || error ? (
          <CAlert color="danger" className="mb-0 py-2">
            {localError ?? error}
          </CAlert>
        ) : null}

        {step === 0 ? (
          <div className="d-flex flex-column gap-3">
            <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
              <div>
                <div className="fw-medium">{d.createManagedCategory}</div>
                <p className="mb-0 mt-1 small text-body-secondary">
                  {d.createManagedCategoryHelp}
                </p>
              </div>
              <Switch
                checked={categoryManaged}
                onChange={setCategoryManaged}
                aria-label={d.createManagedCategoryAria}
              />
            </div>
            {categoryManaged ? (
              <div className="d-flex align-items-end gap-2">
                <div>
                  <CFormLabel>{d.categoryIconOptional}</CFormLabel>
                  <DiscordEmojiPicker
                    value={categoryEmoji}
                    onChange={setCategoryEmoji}
                    placeholder={d.iconPlaceholder}
                  />
                </div>
                <div className="flex-grow-1">
                  <CFormLabel>{d.categoryName}</CFormLabel>
                  <CFormInput
                    value={categoryName}
                    maxLength={90}
                    onChange={(e) => setCategoryName(e.target.value)}
                  />
                </div>
              </div>
            ) : (
              <CAlert color="secondary" className="mb-0 py-2 small">
                {d.topLevelAlert}
              </CAlert>
            )}
          </div>
        ) : null}

        {step === 1 ? (
          <div className="d-flex flex-column gap-3">
            {groups.map((group) => (
              <div
                key={group.key}
                className="border rounded p-3 d-flex flex-column gap-2"
              >
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
                        {d.newChannel}
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
                        {d.existingChannel}
                      </Button>
                    </div>
                  ) : null}
                </div>
                {group.included ? (
                  group.mode === "new" ? (
                    <div className="d-flex align-items-end gap-2">
                      <div>
                        <CFormLabel className="small">
                          {d.iconOptional}
                        </CFormLabel>
                        <DiscordEmojiPicker
                          value={group.newEmoji}
                          onChange={(value) =>
                            patchGroup(group.key, { newEmoji: value })
                          }
                          placeholder={d.iconPlaceholder}
                        />
                      </div>
                      <div className="flex-grow-1">
                        <CFormLabel className="small">{d.channelName}</CFormLabel>
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
                      <option value="">{d.selectChannel}</option>
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
                {d.noGroupsSelected}
              </CAlert>
            ) : (
              includedGroups.map((group) => (
                <div
                  key={group.key}
                  className="border rounded p-3 d-flex flex-column gap-2"
                >
                  <div className="d-flex align-items-center justify-content-between gap-2">
                    <span className="fw-semibold">{group.label}</span>
                    <div className="d-flex align-items-center gap-2">
                      <span className="small text-body-secondary">
                        {d.groupColor}
                      </span>
                      <EmbedColorPicker
                        value={group.defaultColorHex}
                        onChange={(hex) =>
                          patchGroup(group.key, { defaultColorHex: hex })
                        }
                        label={d.groupColor}
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
                            label={d.customColor}
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
                              label={d.eventColor}
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
              <div className="fw-semibold mb-1">{d.stepCategory}</div>
              <div className="small text-body-secondary">
                {categoryManaged
                  ? formatDict(d.willCreateCategory, {
                      name: composeCategoryName(categoryEmoji, categoryName),
                    })
                  : d.noManagedCategory}
              </div>
            </div>
            <div className="border rounded p-3 d-flex flex-column gap-2">
              <div className="fw-semibold">{d.channelsAndEvents}</div>
              {includedGroups.map((group) => {
                const enabledEvents = group.events.filter(
                  (e) => e.enabled,
                ).length;
                return (
                  <div
                    key={group.key}
                    className="d-flex align-items-center justify-content-between gap-2 small"
                  >
                    <span>
                      <Badge variant="neutral">{group.label}</Badge>{" "}
                      {group.mode === "new"
                        ? `#${composeChannelName(group.newEmoji, group.newName)} ${d.newSuffix}`
                        : `#${channels.find((c) => c.id === group.channelId)?.name ?? "?"}`}
                    </span>
                    <span className="text-body-secondary">
                      {formatDict(
                        enabledEvents === 1 ? d.eventCount : d.eventCountPlural,
                        { count: enabledEvents },
                      )}
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
            {d.back}
          </Button>
          {step < steps.length - 1 ? (
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
                setStep((s) => Math.min(steps.length - 1, s + 1));
              }}
            >
              {d.next}
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => void handleCreate()}
              disabled={busy}
            >
              {busy ? d.creating : d.createLogging}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
