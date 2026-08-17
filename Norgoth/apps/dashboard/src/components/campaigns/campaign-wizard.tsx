"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  CAlert,
  CCol,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CRow,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RoleMultiPicker } from "@/components/ui/role-multi-picker";
import { ChannelSelect } from "@/components/ui/channel-select";
import {
  RefreshChannelsButton,
  RolePickerToolbar,
} from "@/components/ui/refresh-channels-button";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { ValidationStatCard } from "@/components/campaigns/validation-stat-card";
import { EmbedColorPicker } from "@/components/discord/embed-color-picker";
import { EmbedMediaPicker } from "@/components/discord/embed-media-picker";
import { MessagePreview } from "@/components/discord/message-preview";
import { addStoredActivity } from "@/lib/activity-storage";
import { buildCampaignPayload } from "@/lib/campaign";
import {
  discordMarkdownToHtml,
  substituteVariables,
} from "@/lib/discord-markdown";
import { isBlankDiscordMarkdown } from "@/lib/discord-markdown-validation";
import {
  defaultCampaignWizardState,
  type CampaignWizardState,
} from "@/types/campaign";
import type { Dictionary } from "@/app/[lang]/dictionaries";
import type { Locale } from "@/i18n/config";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { formatDict } from "@/lib/locale-dict";
import { useCampaignsStore } from "@/stores/campaigns-store";
import { useCampaignWizardDraftStore } from "@/stores/campaign-wizard-draft-store";
import { useFirstGuild } from "@/lib/use-first-guild";

const CAMPAIGN_VARIABLES = ["{user_name}", "{server_name}", "{campaign_name}"];

const MINIMUM_SCHEDULE_DELAY_MS = 2 * 60 * 1000;

type CampaignWizardProps = {
  lang: Locale;
  dict: Dictionary;
  /** When set, the wizard edits this campaign via PATCH instead of creating. */
  editCampaign?: {
    id: string;
    title?: string;
    message?: string;
    delivery_target?: "channel" | "dm";
    discord_channel_id?: string | null;
    dm_include_role_ids?: string[];
    dm_exclude_role_ids?: string[];
    launch_at?: string | null;
    platform_messages?: {
      discord?: {
        type?: string;
        title?: string;
        color?: string | number | null;
        thumbnail_url?: string | null;
        image_url?: string | null;
      };
    };
    raw_payload?: { description?: string };
  };
};

type WizardRole = {
  id: string;
  name: string;
  color: string;
};

type WizardMember = {
  id: string;
  name: string;
  display_name: string;
  bot: boolean;
  role_ids: string[];
};

function buildLaunchAt(state: CampaignWizardState) {
  if (state.launch.launchMode !== "scheduled") {
    return null;
  }

  if (!state.launch.scheduledDate || !state.launch.scheduledTime) {
    return null;
  }

  return new Date(
    `${state.launch.scheduledDate}T${state.launch.scheduledTime}:00`,
  ).toISOString();
}

function validateLaunchAt(
  state: CampaignWizardState,
  copy: Dictionary["campaignWizard"],
) {
  if (state.launch.launchMode !== "scheduled") {
    return null;
  }

  const launchAt = buildLaunchAt(state);

  if (!launchAt) {
    return copy.scheduleNeedDateTime;
  }

  const launchDate = new Date(launchAt);
  const minimumAllowedDate = new Date(Date.now() + MINIMUM_SCHEDULE_DELAY_MS);

  if (Number.isNaN(launchDate.getTime())) {
    return copy.scheduleInvalid;
  }

  if (launchDate.getTime() < minimumAllowedDate.getTime()) {
    return copy.scheduleTooSoon;
  }

  return null;
}

function initialStateFromCampaign(
  campaign: NonNullable<CampaignWizardProps["editCampaign"]>,
): CampaignWizardState {
  const discordMessage = campaign.platform_messages?.discord;
  const launchAt = campaign.launch_at ? new Date(campaign.launch_at) : null;
  const hasValidLaunch = launchAt !== null && !Number.isNaN(launchAt.getTime());

  return {
    basics: {
      name: campaign.title ?? "",
      description: campaign.raw_payload?.description ?? "",
    },
    audience: {
      deliveryTarget: campaign.delivery_target === "dm" ? "dm" : "channel",
      channelId: campaign.discord_channel_id ?? "",
      includeRoleIds: campaign.dm_include_role_ids ?? [],
      excludeRoleIds: campaign.dm_exclude_role_ids ?? [],
    },
    message: {
      messageType: discordMessage?.type === "discord_text" ? "text" : "embed",
      subject: discordMessage?.title ?? campaign.title ?? "",
      body: campaign.message ?? "",
      embedColor:
        typeof discordMessage?.color === "string"
          ? discordMessage.color
          : typeof discordMessage?.color === "number"
            ? `#${discordMessage.color.toString(16).padStart(6, "0")}`
            : "#5865f2",
      embedThumbnailUrl: discordMessage?.thumbnail_url ?? "",
      embedImageUrl: discordMessage?.image_url ?? "",
    },
    launch: {
      launchMode: hasValidLaunch ? "scheduled" : "now",
      scheduledDate: hasValidLaunch
        ? launchAt.toISOString().slice(0, 10)
        : "",
      scheduledTime: hasValidLaunch
        ? launchAt.toTimeString().slice(0, 5)
        : "",
    },
  };
}

function RoleFilterPicker({
  label,
  hint,
  roles,
  selected,
  onChange,
  searchPlaceholder,
  emptyMessage,
}: {
  label: string;
  hint: string;
  roles: WizardRole[];
  selected: string[];
  onChange: (ids: string[]) => void;
  searchPlaceholder: string;
  emptyMessage: string;
}) {
  return (
    <div className="d-flex flex-column gap-2">
      <div>
        <div className="fw-medium">{label}</div>
        <div className="small text-body-secondary">{hint}</div>
      </div>

      {roles.length === 0 ? (
        <CAlert color="secondary" className="mb-0">
          {emptyMessage}
        </CAlert>
      ) : (
        <RoleMultiPicker
          roles={roles.map((role) => ({
            id: role.id,
            name: role.name,
            managed: false,
          }))}
          selectedIds={selected}
          onChange={onChange}
          excludeManaged={false}
          searchPlaceholder={searchPlaceholder}
        />
      )}
    </div>
  );
}

function ChoiceCard({
  selected,
  onClick,
  title,
  description,
}: {
  selected: boolean;
  onClick: () => void;
  title: string;
  description?: string;
}) {
  return (
    <Card
      variant={selected ? "interactive" : "static"}
      onClick={onClick}
      className="h-100"
    >
      <div className={`fw-medium ${selected ? "text-primary" : ""}`}>
        {title}
      </div>
      {description ? (
        <div className="mt-1 small text-body-secondary">{description}</div>
      ) : null}
    </Card>
  );
}

function SidePanel({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="border rounded p-4 h-100">
      {children}
    </div>
  );
}

function StatBox({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="border rounded p-3">
      <div className="small text-body-secondary">{label}</div>
      <div className="mt-1 fs-3 fw-semibold">{value}</div>
    </div>
  );
}

export function CampaignWizard({ lang, dict, editCampaign }: CampaignWizardProps) {
  const router = useRouter();
  const wizardCopy = dict.campaignWizard;
  const isEdit = Boolean(editCampaign);

  const step = useCampaignsStore((s) => s.wizardStep);
  const setStep = useCampaignsStore((s) => s.setWizardStep);
  const wizardState = useCampaignsStore((s) => s.wizardState);
  const setWizardState = useCampaignsStore((s) => s.setWizardState);
  const resetWizard = useCampaignsStore((s) => s.resetWizard);

  const draft = useCampaignWizardDraftStore((s) => s.draft);
  const hasDraft = useCampaignWizardDraftStore((s) => s.hasDraft);
  const saveDraft = useCampaignWizardDraftStore((s) => s.saveDraft);
  const discardDraft = useCampaignWizardDraftStore((s) => s.discardDraft);
  const startNewDraft = useCampaignWizardDraftStore((s) => s.startNew);
  const bannerDismissed = useCampaignWizardDraftStore((s) => s.bannerDismissed);
  const setBannerDismissed = useCampaignWizardDraftStore(
    (s) => s.setBannerDismissed,
  );
  const [draftHydrated, setDraftHydrated] = useState(false);
  const [descriptionEditorSeed, setDescriptionEditorSeed] = useState(0);

  useEffect(() => {
    if (isEdit) {
      resetWizard(initialStateFromCampaign(editCampaign!));
      setDescriptionEditorSeed((n) => n + 1);
      setDraftHydrated(true);
      return;
    }

    // Offer restore via banner; start empty until Continue / Start new.
    resetWizard(defaultCampaignWizardState);
    setDescriptionEditorSeed((n) => n + 1);
    setBannerDismissed(false);
    setDraftHydrated(true);
    // Intentionally key on the campaign id only: depending on the whole
    // `editCampaign` object would re-run (and reset the wizard, discarding
    // in-progress edits) whenever the parent passes a new object reference.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editCampaign?.id, isEdit, resetWizard, setBannerDismissed]);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const showDraftBanner =
    !isEdit && draftHydrated && hasDraft() && !bannerDismissed;

  const { guildId: selectedGuildId, selectedGuild, resources: storeResources } =
    useFirstGuild();
  const [guildId, setGuildId] = useState<string | null>(null);
  const [guildName, setGuildName] = useState<string>(wizardCopy.defaultServerName);
  const channels = storeResources?.channels ?? [];
  const roles: WizardRole[] = (storeResources?.roles ?? []).map((role) => ({
    id: role.id,
    name: role.name,
    color: role.color ?? "#99aab5",
  }));
  const [members, setMembers] = useState<WizardMember[]>([]);
  const [resourcesError, setResourcesError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadGuildData() {
      try {
        const [healthResponse, workerResponse] = await Promise.all([
          fetch(apiUrl(`/bot/health`), { cache: "no-store" }),
          fetch(apiUrl(`/campaigns/worker/health`), { cache: "no-store" }),
        ]);
        if (!healthResponse.ok || !workerResponse.ok) {
          if (!cancelled) {
            setResourcesError(wizardCopy.guildApiError);
          }
          return;
        }
        const health = await healthResponse.json();
        const worker = await workerResponse.json();

        if (!health?.connected) {
          if (!cancelled) {
            setResourcesError(
              health?.stale
                ? wizardCopy.staleHeartbeat
                : wizardCopy.botOfflineDelivery
            );
          }
          return;
        }
        if (!worker?.online) {
          if (!cancelled) {
            setResourcesError(wizardCopy.workerOfflineDelivery);
          }
          return;
        }
        if (!selectedGuildId || selectedGuild?.bot_installed === false) {
          if (!cancelled) {
            setResourcesError(wizardCopy.botNotInGuild);
          }
          return;
        }

        if (!cancelled) {
          setGuildId(selectedGuildId);
          setGuildName(
            String(selectedGuild?.name ?? wizardCopy.defaultServerName)
          );
          setResourcesError(null);
        }

        const membersResponse = await fetch(
          apiUrl(`/guilds/${selectedGuildId}/members`),
          {
            cache: "no-store",
            credentials: "include",
          },
        );

        if (membersResponse.ok) {
          const snapshot = await membersResponse.json();

          if (!cancelled && Array.isArray(snapshot.members)) {
            setMembers(snapshot.members as WizardMember[]);
          }
        }
      } catch {
        if (!cancelled) {
          setResourcesError(wizardCopy.guildApiError);
        }
      }
    }

    void loadGuildData();

    return () => {
      cancelled = true;
    };
  }, [
    selectedGuild?.bot_installed,
    selectedGuild?.name,
    selectedGuildId,
    wizardCopy.botNotInGuild,
    wizardCopy.botOfflineDelivery,
    wizardCopy.defaultServerName,
    wizardCopy.guildApiError,
    wizardCopy.staleHeartbeat,
    wizardCopy.workerOfflineDelivery,
  ]);

  const isDM = wizardState.audience.deliveryTarget === "dm";

  const dmRecipients = useMemo(() => {
    const include = wizardState.audience.includeRoleIds;
    const exclude = wizardState.audience.excludeRoleIds;

    return members.filter((member) => {
      if (member.bot) return false;

      const memberRoles = member.role_ids ?? [];

      if (include.length > 0 && !memberRoles.some((id) => include.includes(id))) {
        return false;
      }

      if (memberRoles.some((id) => exclude.includes(id))) {
        return false;
      }

      return true;
    });
  }, [members, wizardState.audience.includeRoleIds, wizardState.audience.excludeRoleIds]);

  const botMemberCount = useMemo(
    () => members.filter((member) => member.bot).length,
    [members],
  );

  const estimatedAudience = isDM ? dmRecipients.length : 1;

  const riskLevel: "low" | "medium" | "high" = useMemo(() => {
    if (!isDM) return "low";
    if (dmRecipients.length > 100) return "high";
    if (dmRecipients.length > 25) return "medium";
    return "low";
  }, [isDM, dmRecipients.length]);

  const scheduleValidationError = useMemo(() => {
    return validateLaunchAt(wizardState, wizardCopy);
  }, [wizardState, wizardCopy]);

  const targetSelected = isDM
    ? dmRecipients.length > 0
    : wizardState.audience.channelId.length > 0;

  const readyToLaunch = useMemo(() => {
    return (
      targetSelected &&
      wizardState.message.body.trim().length > 10 &&
      wizardState.basics.name.trim().length > 2 &&
      !scheduleValidationError
    );
  }, [
    targetSelected,
    wizardState.message.body,
    wizardState.basics.name,
    scheduleValidationError,
  ]);

  const stepLabel = dict.campaignWizard.stepOf
    .replace("{current}", String(step))
    .replace("{total}", "5");

  const previewSampleValues = useMemo(
    () => ({
      // Channel campaigns have no recipient — match runtime USER_NAME_FALLBACK.
      // DM preview uses a sample display name; runtime resolves per recipient.
      "{user_name}": isDM ? "Alice" : "member",
      "{server_name}": guildName,
      "{campaign_name}":
        wizardState.basics.name.trim() || wizardCopy.defaultCampaignName,
    }),
    [isDM, guildName, wizardState.basics.name, wizardCopy.defaultCampaignName],
  );

  const previewHtml = useMemo(() => {
    const substituted = substituteVariables(
      wizardState.message.body,
      previewSampleValues,
    );
    return discordMarkdownToHtml(substituted);
  }, [wizardState.message.body, previewSampleValues]);

  function setRoleList(
    list: "includeRoleIds" | "excludeRoleIds",
    ids: string[]
  ) {
    setWizardState((prev) => ({
      ...prev,
      audience: {
        ...prev.audience,
        [list]: ids,
      },
    }));
  }

  async function handleLaunchCampaign() {
    try {
      setIsSubmitting(true);
      setSubmitError(null);
      setSubmitMessage(null);

      const validationError = validateLaunchAt(wizardState, wizardCopy);

      if (validationError) {
        setSubmitError(validationError);
        return;
      }

      if (!isDM && !wizardState.audience.channelId) {
        setSubmitError(wizardCopy.selectChannelFirst);
        return;
      }

      if (isDM && dmRecipients.length === 0) {
        setSubmitError(wizardCopy.roleFiltersEmpty);
        return;
      }

      const launchAt = buildLaunchAt(wizardState);
      const payload = {
        ...buildCampaignPayload(wizardState, {
          guildId,
          audienceCount: estimatedAudience,
          launchAt,
          riskLevel,
        }),
        description: isBlankDiscordMarkdown(wizardState.basics.description)
          ? ""
          : wizardState.basics.description.trim(),
      };

      const url = isEdit
        ? apiUrl(`/campaigns/${editCampaign!.id}`)
        : apiUrl(`/campaigns`);

      const response = await fetch(url, {
        method: isEdit ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(
          isEdit
            ? {
                title: payload.title,
                name: payload.name,
                description: payload.description,
                message: payload.message,
                body: wizardState.message.body.trim(),
                audience_count: estimatedAudience,
                launch_at: launchAt,
                risk_level: riskLevel,
                delivery_target: wizardState.audience.deliveryTarget,
                guild_id: guildId,
                discord_channel_id: isDM
                  ? null
                  : wizardState.audience.channelId || null,
                dm_include_role_ids: wizardState.audience.includeRoleIds,
                dm_exclude_role_ids: wizardState.audience.excludeRoleIds,
              }
            : payload,
        ),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || wizardCopy.requestFailed);
      }

      const result = await response.json();
      const createdName = result.title || wizardState.basics.name.trim();

      addStoredActivity({
        id: `act_${Date.now()}`,
        title: isEdit ? wizardCopy.campaignUpdated : wizardCopy.campaignCreated,
        meta: createdName,
        type: "success",
        created_at: new Date().toISOString(),
      });

      setSubmitMessage(
        isEdit
          ? `${wizardCopy.campaignUpdated}: ${createdName}`
          : launchAt
            ? `${wizardCopy.campaignScheduled}: ${createdName}`
            : `${wizardCopy.campaignQueued}: ${createdName}`,
      );

      if (!isEdit) {
        discardDraft();
      }

      setTimeout(() => {
        router.push(
          isEdit
            ? `/${lang}/campaigns/${editCampaign!.id}`
            : `/${lang}/campaigns`,
        );
        router.refresh();
      }, 800);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : wizardCopy.unknownError;
      setSubmitError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card>
      <div className="d-flex flex-column gap-4">
        {showDraftBanner ? (
          <CAlert color="info" className="mb-0">
            <div className="d-flex flex-wrap align-items-center justify-content-between gap-3">
              <div>
                <div className="fw-semibold">{wizardCopy.draftFoundTitle}</div>
                <div className="small">
                  {formatDict(wizardCopy.draftFoundBody, {
                    when: draft?.updatedAt
                      ? formatDateTime(draft.updatedAt, lang)
                      : wizardCopy.recently,
                  })}
                </div>
              </div>
              <div className="d-flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    if (draft) {
                      resetWizard(draft.wizardState);
                      setStep(draft.step);
                      setDescriptionEditorSeed((n) => n + 1);
                    }
                    setBannerDismissed(true);
                  }}
                >
                  {wizardCopy.continueDraft}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    discardDraft();
                    resetWizard(defaultCampaignWizardState);
                    setDescriptionEditorSeed((n) => n + 1);
                    setStep(1);
                  }}
                >
                  {wizardCopy.discardDraft}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    startNewDraft();
                    resetWizard(defaultCampaignWizardState);
                    setStep(1);
                    setBannerDismissed(true);
                  }}
                >
                  {wizardCopy.startNewDraft}
                </Button>
              </div>
            </div>
          </CAlert>
        ) : null}

        {!isEdit ? (
          <div className="d-flex justify-content-end">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                saveDraft(step, wizardState);
                setSubmitMessage(wizardCopy.draftSaved);
              }}
            >
              {wizardCopy.saveDraft}
            </Button>
          </div>
        ) : null}

        <div className="d-flex flex-column gap-2">
          <div className="d-flex flex-wrap align-items-center gap-3">
            {[1, 2, 3, 4, 5].map((item) => {
              const isActive = item === step;
              const isPassed = item < step;

              return (
                <div key={item} className="d-flex align-items-center gap-3">
                  <div
                    className={[
                      "d-flex align-items-center justify-content-center border rounded-circle",
                      isActive
                        ? "border-primary text-primary"
                        : isPassed
                          ? "border-success text-success"
                          : "text-body-secondary",
                    ].join(" ")}
                    style={{ width: "2.25rem", height: "2.25rem" }}
                  >
                    {item}
                  </div>

                  {item < 5 ? (
                    <div
                      className="d-none d-md-block border-top"
                      style={{ width: "2.5rem" }}
                    />
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="small text-body-secondary">{stepLabel}</div>
        </div>

        {step === 1 && (
          <CRow className="g-4">
            <CCol xl={8}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h2 className="h5 mb-1">{dict.campaignWizard.basicsTitle}</h2>
                  <p className="mb-0 text-body-secondary small">
                    {dict.campaignWizard.basicsDescription}
                  </p>
                </div>

                <div>
                  <CFormLabel>{dict.campaignWizard.campaignName}</CFormLabel>
                  <CFormInput
                    value={wizardState.basics.name}
                    onChange={(e) =>
                      setWizardState((prev) => ({
                        ...prev,
                        basics: {
                          ...prev.basics,
                          name: e.target.value,
                        },
                      }))
                    }
                    placeholder={wizardCopy.campaignNamePlaceholder}
                  />
                </div>

                <div>
                  <CFormLabel>
                    {dict.campaignWizard.internalDescription}
                  </CFormLabel>
                  <RichMessageEditor
                    key={`campaign-internal-desc-${editCampaign?.id ?? "new"}-${descriptionEditorSeed}`}
                    value={wizardState.basics.description}
                    onChange={(markdown) =>
                      setWizardState((prev) => ({
                        ...prev,
                        basics: {
                          ...prev.basics,
                          description: isBlankDiscordMarkdown(markdown)
                            ? ""
                            : markdown,
                        },
                      }))
                    }
                    height={180}
                    placeholder={wizardCopy.internalNotePlaceholder}
                  />
                  <p className="mt-1 mb-0 small text-body-secondary">
                    {wizardCopy.formattingInternalNote}
                  </p>
                </div>
              </div>
            </CCol>

            <CCol xl={4}>
              <SidePanel>
                <h3 className="h6">{dict.campaignWizard.stepSummary}</h3>
                <p className="mb-0 text-body-secondary small">
                  {dict.campaignWizard.basicsSummary}
                </p>
              </SidePanel>
            </CCol>
          </CRow>
        )}

        {step === 2 && (
          <CRow className="g-4">
            <CCol xl={8}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h2 className="h5 mb-1">{dict.campaignWizard.audienceTitle}</h2>
                  <p className="mb-0 text-body-secondary small">
                    {wizardCopy.audienceDescription}
                  </p>
                </div>

                {resourcesError ? (
                  <CAlert color="warning" className="mb-0">
                    {resourcesError}
                  </CAlert>
                ) : null}

                <div>
                  <CFormLabel>{wizardCopy.deliveryTarget}</CFormLabel>
                  <CRow className="g-3">
                    {[
                      {
                        value: "channel" as const,
                        label: wizardCopy.channelBroadcast,
                        description: wizardCopy.channelBroadcastDesc,
                      },
                      {
                        value: "dm" as const,
                        label: wizardCopy.memberDms,
                        description: wizardCopy.memberDmsDesc,
                      },
                    ].map((option) => (
                      <CCol key={option.value} md={6}>
                        <ChoiceCard
                          selected={
                            wizardState.audience.deliveryTarget === option.value
                          }
                          onClick={() =>
                            setWizardState((prev) => ({
                              ...prev,
                              audience: {
                                ...prev.audience,
                                deliveryTarget: option.value,
                              },
                            }))
                          }
                          title={option.label}
                          description={option.description}
                        />
                      </CCol>
                    ))}
                  </CRow>
                </div>

                {!isDM ? (
                  <div className="border rounded p-3 d-flex flex-column gap-3">
                    <div className="d-flex flex-wrap align-items-start justify-content-between gap-2">
                      <div>
                        <h3 className="h6 mb-1">
                          {wizardCopy.discordDeliveryChannel}
                        </h3>
                        <p className="mb-0 text-body-secondary small">
                          {wizardCopy.discordDeliveryChannelDesc}
                        </p>
                      </div>
                      <RefreshChannelsButton />
                    </div>

                    <ChannelSelect
                      channels={channels}
                      value={wizardState.audience.channelId}
                      onChange={(value) =>
                        setWizardState((prev) => ({
                          ...prev,
                          audience: {
                            ...prev.audience,
                            channelId: value,
                          },
                        }))
                      }
                      emptyLabel={wizardCopy.selectChannel}
                    />

                    {!wizardState.audience.channelId ? (
                      <CAlert color="danger" className="mb-0">
                        {wizardCopy.selectDeliveryChannel}
                      </CAlert>
                    ) : null}
                  </div>
                ) : (
                  <div className="border rounded p-3 d-flex flex-column gap-3">
                    <RolePickerToolbar label={wizardCopy.dmAudienceFilters} />
                    <p className="mb-0 text-body-secondary small">
                      {wizardCopy.dmAudienceFiltersDesc}
                    </p>

                    <RoleFilterPicker
                      label={dict.campaignWizard.includeRoles}
                      hint={wizardCopy.includeRolesHint}
                      roles={roles}
                      selected={wizardState.audience.includeRoleIds}
                      onChange={(ids) => setRoleList("includeRoleIds", ids)}
                      searchPlaceholder={wizardCopy.searchRoles}
                      emptyMessage={wizardCopy.noRolesFound}
                    />

                    <RoleFilterPicker
                      label={dict.campaignWizard.excludeRoles}
                      hint={wizardCopy.excludeRolesHint}
                      roles={roles}
                      selected={wizardState.audience.excludeRoleIds}
                      onChange={(ids) => setRoleList("excludeRoleIds", ids)}
                      searchPlaceholder={wizardCopy.searchRoles}
                      emptyMessage={wizardCopy.noRolesFound}
                    />

                    {dmRecipients.length === 0 ? (
                      <CAlert color="danger" className="mb-0">
                        {members.length === 0
                          ? wizardCopy.noMemberSnapshot
                          : wizardCopy.filtersMatchNone}
                      </CAlert>
                    ) : null}
                  </div>
                )}
              </div>
            </CCol>

            <CCol xl={4}>
              <SidePanel>
                <div className="d-flex flex-column gap-3">
                  <div className="d-flex align-items-center justify-content-between gap-3">
                    <h3 className="h6 mb-0">
                      {dict.campaignWizard.audienceSummary}
                    </h3>
                    <Badge variant="info">
                      {isDM ? wizardCopy.memberDms : wizardCopy.channelLabel}
                    </Badge>
                  </div>

                  <StatBox
                    label={
                      isDM
                        ? wizardCopy.dmRecipients
                        : dict.campaignWizard.estimatedAudience
                    }
                    value={
                      isDM
                        ? dmRecipients.length
                        : wizardState.audience.channelId
                          ? wizardCopy.oneChannel
                          : "—"
                    }
                  />

                  {isDM ? (
                    <StatBox label={wizardCopy.excludedBots} value={botMemberCount} />
                  ) : null}

                  <p className="mb-0 text-body-secondary small">
                    {isDM
                      ? wizardCopy.dmRateLimitNote
                      : wizardCopy.channelPostNote}
                  </p>
                </div>
              </SidePanel>
            </CCol>
          </CRow>
        )}

        {step === 3 && (
          <CRow className="g-4">
            <CCol xl={8}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h2 className="h5 mb-1">{dict.campaignWizard.messageTitle}</h2>
                  <p className="mb-0 text-body-secondary small">
                    {dict.campaignWizard.messageDescription}
                  </p>
                </div>

                <div>
                  <CFormLabel>{dict.campaignWizard.messageType}</CFormLabel>
                  <CRow className="g-3">
                    {[
                      {
                        value: "text" as const,
                        label: dict.campaignWizard.textMessage,
                      },
                      {
                        value: "embed" as const,
                        label: dict.campaignWizard.embedMessage,
                      },
                    ].map((option) => (
                      <CCol key={option.value} md={6}>
                        <ChoiceCard
                          selected={
                            wizardState.message.messageType === option.value
                          }
                          onClick={() =>
                            setWizardState((prev) => ({
                              ...prev,
                              message: {
                                ...prev.message,
                                messageType: option.value,
                              },
                            }))
                          }
                          title={option.label}
                        />
                      </CCol>
                    ))}
                  </CRow>
                </div>

                {wizardState.message.messageType === "embed" ? (
                  <>
                    <div>
                      <CFormLabel>
                        {dict.campaignWizard.messageSubject}
                      </CFormLabel>
                      <CFormInput
                        value={wizardState.message.subject}
                        onChange={(e) =>
                          setWizardState((prev) => ({
                            ...prev,
                            message: {
                              ...prev.message,
                              subject: e.target.value,
                            },
                          }))
                        }
                        placeholder={wizardCopy.embedTitlePlaceholder}
                      />
                    </div>

                    <div>
                      <CFormLabel className="d-block">
                        {wizardCopy.embedColorLabel}
                      </CFormLabel>
                      <EmbedColorPicker
                        value={wizardState.message.embedColor}
                        onChange={(hex) =>
                          setWizardState((prev) => ({
                            ...prev,
                            message: { ...prev.message, embedColor: hex },
                          }))
                        }
                      />
                    </div>

                    <CRow className="g-3">
                      <CCol md={6}>
                        <EmbedMediaPicker
                          label={wizardCopy.thumbnailLabel}
                          helper={wizardCopy.thumbnailHelper}
                          value={wizardState.message.embedThumbnailUrl}
                          guildId={guildId ?? undefined}
                          onChange={(url) =>
                            setWizardState((prev) => ({
                              ...prev,
                              message: {
                                ...prev.message,
                                embedThumbnailUrl: url,
                              },
                            }))
                          }
                        />
                      </CCol>
                      <CCol md={6}>
                        <EmbedMediaPicker
                          label={wizardCopy.mainImageLabel}
                          helper={wizardCopy.mainImageHelper}
                          value={wizardState.message.embedImageUrl}
                          guildId={guildId ?? undefined}
                          banner
                          equalizeToThumbnail
                          onChange={(url) =>
                            setWizardState((prev) => ({
                              ...prev,
                              message: {
                                ...prev.message,
                                embedImageUrl: url,
                              },
                            }))
                          }
                        />
                      </CCol>
                    </CRow>
                  </>
                ) : null}

                <div>
                  <CFormLabel>{dict.campaignWizard.messageBody}</CFormLabel>
                  <RichMessageEditor
                    value={wizardState.message.body}
                    onChange={(markdown) =>
                      setWizardState((prev) => ({
                        ...prev,
                        message: {
                          ...prev.message,
                          body: markdown,
                        },
                      }))
                    }
                    variables={CAMPAIGN_VARIABLES}
                    placeholder={wizardCopy.messageBodyPlaceholder}
                  />
                  <p className="mt-2 mb-0 small text-body-secondary">
                    {wizardCopy.formattingSendNote}
                  </p>
                </div>
              </div>
            </CCol>

            <CCol xl={4}>
              <SidePanel>
                <div className="d-flex flex-column gap-3">
                  <div className="d-flex align-items-center justify-content-between gap-3">
                    <h3 className="h6 mb-0">{dict.campaignWizard.preview}</h3>
                    <Badge variant="neutral">
                      {wizardState.message.messageType}
                    </Badge>
                  </div>

                  {wizardState.message.messageType === "embed" ? (
                    <MessagePreview
                      embed={{
                        title: substituteVariables(
                          wizardState.message.subject ||
                            wizardState.basics.name ||
                            wizardCopy.defaultCampaignName,
                          previewSampleValues,
                        ),
                        description: substituteVariables(
                          wizardState.message.body,
                          previewSampleValues,
                        ),
                        color: wizardState.message.embedColor,
                        thumbnail_url:
                          wizardState.message.embedThumbnailUrl || undefined,
                        image_url:
                          wizardState.message.embedImageUrl || undefined,
                        footer: wizardCopy.embedFooter,
                      }}
                      mode="embed"
                      showImagePlaceholders
                    />
                  ) : (
                    <div className="border rounded p-3 overflow-hidden">
                      <div
                        className="prose-preview text-break small"
                        dangerouslySetInnerHTML={{
                          __html:
                            previewHtml ||
                            `<p class="text-body-secondary">${wizardCopy.messageBodyPreview}</p>`,
                        }}
                      />
                    </div>
                  )}

                  <p className="mb-0 text-body-secondary small">
                    {formatDict(wizardCopy.previewSampleNote, {
                      userSample: previewSampleValues["{user_name}"],
                      serverName: guildName,
                    })}
                  </p>
                </div>
              </SidePanel>
            </CCol>
          </CRow>
        )}

        {step === 4 && (
          <CRow className="g-4">
            <CCol xl={8}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h2 className="h5 mb-1">
                    {dict.campaignWizard.validationTitle}
                  </h2>
                  <p className="mb-0 text-body-secondary small">
                    {dict.campaignWizard.validationDescription}
                  </p>
                </div>

                <CRow className="g-3">
                  <CCol md={6} xl={4}>
                    <ValidationStatCard
                      label={
                        isDM
                          ? wizardCopy.dmRecipients
                          : wizardCopy.channelDeliveries
                      }
                      value={estimatedAudience}
                      tone="success"
                    />
                  </CCol>
                  {isDM ? (
                    <>
                      <CCol md={6} xl={4}>
                        <ValidationStatCard
                          label={wizardCopy.botsExcluded}
                          value={botMemberCount}
                          tone="warning"
                        />
                      </CCol>
                      <CCol md={6} xl={4}>
                        <ValidationStatCard
                          label={wizardCopy.roleFiltersActive}
                          value={
                            wizardState.audience.includeRoleIds.length +
                            wizardState.audience.excludeRoleIds.length
                          }
                        />
                      </CCol>
                    </>
                  ) : (
                    <CCol md={6} xl={4}>
                      <ValidationStatCard
                        label={wizardCopy.serverMembersReached}
                        value={members.filter((m) => !m.bot).length}
                      />
                    </CCol>
                  )}
                </CRow>
              </div>
            </CCol>

            <CCol xl={4}>
              <SidePanel>
                <div className="d-flex flex-column gap-3">
                  <h3 className="h6 mb-0">
                    {dict.campaignWizard.validationSummary}
                  </h3>

                  <div className="border rounded p-3">
                    <div className="small text-body-secondary">
                      {dict.campaignWizard.riskLevel}
                    </div>
                    <div className="mt-2">
                      <Badge
                        variant={
                          riskLevel === "high"
                            ? "danger"
                            : riskLevel === "medium"
                              ? "warning"
                              : "success"
                        }
                      >
                        {riskLevel === "high"
                          ? dict.campaignDetail.high
                          : riskLevel === "medium"
                            ? dict.campaignDetail.medium
                            : dict.campaignDetail.low}
                      </Badge>
                    </div>
                    {isDM && riskLevel !== "low" ? (
                      <p className="mt-2 mb-0 small text-body-secondary">
                        {wizardCopy.largeDmRiskNote}
                      </p>
                    ) : null}
                  </div>

                  <div className="border rounded p-3">
                    <div className="small text-body-secondary">
                      {dict.campaignWizard.launchReadiness}
                    </div>
                    <div className="mt-2">
                      <Badge variant={readyToLaunch ? "success" : "warning"}>
                        {readyToLaunch
                          ? dict.campaignWizard.readyToLaunch
                          : dict.campaignWizard.needsReview}
                      </Badge>
                    </div>
                  </div>
                </div>
              </SidePanel>
            </CCol>
          </CRow>
        )}

        {step === 5 && (
          <CRow className="g-4">
            <CCol xl={8}>
              <div className="d-flex flex-column gap-3">
                <div>
                  <h2 className="h5 mb-1">{dict.campaignWizard.launchTitle}</h2>
                  <p className="mb-0 text-body-secondary small">
                    {dict.campaignWizard.launchDescription}
                  </p>
                </div>

                <div>
                  <CFormLabel>{dict.campaignWizard.launchMode}</CFormLabel>
                  <CRow className="g-3">
                    {[
                      {
                        value: "now" as const,
                        label: dict.campaignWizard.startNow,
                      },
                      {
                        value: "scheduled" as const,
                        label: dict.campaignWizard.scheduleForLater,
                      },
                    ].map((option) => (
                      <CCol key={option.value} md={6}>
                        <ChoiceCard
                          selected={
                            wizardState.launch.launchMode === option.value
                          }
                          onClick={() =>
                            setWizardState((prev) => ({
                              ...prev,
                              launch: {
                                ...prev.launch,
                                launchMode: option.value,
                              },
                            }))
                          }
                          title={option.label}
                        />
                      </CCol>
                    ))}
                  </CRow>
                </div>

                {wizardState.launch.launchMode === "scheduled" && (
                  <>
                    <CRow className="g-3">
                      <CCol md={6}>
                        <CFormLabel>
                          {dict.campaignWizard.scheduledDate}
                        </CFormLabel>
                        <CFormInput
                          type="date"
                          value={wizardState.launch.scheduledDate}
                          onChange={(e) =>
                            setWizardState((prev) => ({
                              ...prev,
                              launch: {
                                ...prev.launch,
                                scheduledDate: e.target.value,
                              },
                            }))
                          }
                        />
                      </CCol>

                      <CCol md={6}>
                        <CFormLabel>
                          {dict.campaignWizard.scheduledTime}
                        </CFormLabel>
                        <CFormInput
                          type="time"
                          value={wizardState.launch.scheduledTime}
                          onChange={(e) =>
                            setWizardState((prev) => ({
                              ...prev,
                              launch: {
                                ...prev.launch,
                                scheduledTime: e.target.value,
                              },
                            }))
                          }
                        />
                      </CCol>
                    </CRow>

                    {scheduleValidationError ? (
                      <CAlert color="danger" className="mb-0">
                        {scheduleValidationError}
                      </CAlert>
                    ) : (
                      <CAlert color="info" className="mb-0">
                        {wizardCopy.scheduleWaitingNote}
                      </CAlert>
                    )}
                  </>
                )}
              </div>
            </CCol>

            <CCol xl={4}>
              <SidePanel>
                <div className="d-flex flex-column gap-3">
                  <h3 className="h6 mb-0">{dict.campaignWizard.finalReview}</h3>

                  <div className="border rounded p-3">
                    <div className="small text-body-secondary">
                      {wizardCopy.delivery}
                    </div>
                    <div className="mt-2 d-flex flex-wrap gap-2">
                      <Badge variant="info">
                        {isDM
                          ? formatDict(wizardCopy.dmToMembers, {
                              count: dmRecipients.length,
                            })
                          : wizardState.audience.channelId
                            ? `#${
                                channels.find(
                                  (c) =>
                                    c.id === wizardState.audience.channelId,
                                )?.name ?? wizardState.audience.channelId
                              }`
                            : wizardCopy.notSelected}
                      </Badge>
                      <Badge variant="neutral">
                        {wizardState.message.messageType === "text"
                          ? dict.campaignWizard.textMessage
                          : dict.campaignWizard.embedMessage}
                      </Badge>
                    </div>
                  </div>

                  <div className="border rounded p-3">
                    <div className="small text-body-secondary">
                      {dict.campaignWizard.finalRiskLevel}
                    </div>
                    <div className="mt-2">
                      <Badge
                        variant={
                          riskLevel === "high"
                            ? "danger"
                            : riskLevel === "medium"
                              ? "warning"
                              : "success"
                        }
                      >
                        {riskLevel === "high"
                          ? dict.campaignDetail.high
                          : riskLevel === "medium"
                            ? dict.campaignDetail.medium
                            : dict.campaignDetail.low}
                      </Badge>
                    </div>
                  </div>

                  <div className="border rounded p-3">
                    <div className="small text-body-secondary">
                      {dict.campaignWizard.launchReadiness}
                    </div>
                    <div className="mt-2">
                      <Badge variant={readyToLaunch ? "success" : "warning"}>
                        {readyToLaunch
                          ? dict.campaignWizard.campaignReady
                          : dict.campaignWizard.campaignNotReady}
                      </Badge>
                    </div>
                  </div>

                  <p className="mb-0 text-body-secondary small">
                    {isEdit
                      ? wizardCopy.saveWithoutLaunch
                      : wizardState.launch.launchMode === "now"
                        ? wizardCopy.launchQueuesNow
                        : dict.campaignWizard.launchNote}
                  </p>

                  <Button
                    className="w-100"
                    variant={readyToLaunch ? "primary" : "secondary"}
                    disabled={!readyToLaunch || isSubmitting}
                    onClick={handleLaunchCampaign}
                  >
                    {isSubmitting
                      ? wizardCopy.submitting
                      : isEdit
                        ? wizardCopy.saveChanges
                        : dict.campaignWizard.launchCampaign}
                  </Button>

                  {submitMessage ? (
                    <CAlert color="success" className="mb-0">
                      {submitMessage}
                    </CAlert>
                  ) : null}

                  {submitError ? (
                    <CAlert color="danger" className="mb-0">
                      {submitError}
                    </CAlert>
                  ) : null}
                </div>
              </SidePanel>
            </CCol>
          </CRow>
        )}

        <div className="d-flex align-items-center justify-content-between gap-3 border-top pt-3">
          <Button
            variant="secondary"
            disabled={step === 1}
            onClick={() => setStep((prev) => Math.max(1, prev - 1))}
          >
            {dict.campaignWizard.back}
          </Button>

          <Button
            disabled={step === 5}
            onClick={() => setStep((prev) => Math.min(5, prev + 1))}
          >
            {dict.campaignWizard.next}
          </Button>
        </div>
      </div>
    </Card>
  );
}
