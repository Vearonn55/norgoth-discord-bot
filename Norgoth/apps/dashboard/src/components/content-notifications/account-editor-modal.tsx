"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CFormCheck,
  CFormInput,
  CFormSelect,
  CFormTextarea,
} from "@coreui/react";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { ChannelSelect } from "@/components/ui/channel-select";
import {
  ChannelPickerToolbar,
  RolePickerToolbar,
} from "@/components/ui/refresh-channels-button";
import { RoleSelect } from "@/components/ui/role-select";
import { MessagePreview } from "@/components/discord/message-preview";
import { PlatformAvatar } from "@/components/content-notifications/platform-avatar";
import { apiUrl } from "@/lib/api";
import {
  webhookEmbedToPreview,
  type DiscordWebhookEmbed,
} from "@/lib/discord/message-payload";
import { formatDict } from "@/lib/locale-dict";
import {
  localizeEventType,
  useContentNotificationsCopy,
  type ContentNotificationsCopy,
} from "@/lib/content-notifications-copy";
import {
  confirmDirtyClose,
  EVENT_TYPES_BY_PLATFORM,
} from "@/lib/cn-url-state";
import { useGuildStore } from "@/stores/guild-store";
import {
  ContentNotificationApiError,
  useContentNotificationsStore,
  type ContentAccount,
  type ContentPlatform,
  type ResolvedCreator,
} from "@/stores/content-notifications-store";

const DEFAULT_LIVE_MESSAGE =
  "{ping_role}\n{account} posted new content!\n\n{title}\n{link}";

const PLATFORM_LABELS: Record<string, string> = {
  youtube: "YouTube",
  twitch: "Twitch",
  kick: "Kick",
  x: "X",
  tiktok: "TikTok",
};

type AccountEditorModalProps = {
  guildId: string;
  mode: "add" | "edit";
  account: ContentAccount | null;
  visible: boolean;
  onClose: () => void;
};

export function AccountEditorModal({
  guildId,
  mode,
  account,
  visible,
  onClose,
}: AccountEditorModalProps) {
  const copy = useContentNotificationsCopy();
  const resources = useGuildStore((s) => s.resources);
  const platforms = useContentNotificationsStore((s) => s.platforms);
  const templates = useContentNotificationsStore((s) => s.templates);
  const styles = useContentNotificationsStore((s) => s.styles);
  const accounts = useContentNotificationsStore((s) => s.accounts);
  const saving = useContentNotificationsStore((s) => s.saving);
  const resolveAccount = useContentNotificationsStore((s) => s.resolveAccount);
  const createAccount = useContentNotificationsStore((s) => s.createAccount);
  const updateAccount = useContentNotificationsStore((s) => s.updateAccount);
  const createTemplate = useContentNotificationsStore((s) => s.createTemplate);
  const updateTemplate = useContentNotificationsStore((s) => s.updateTemplate);

  const [platform, setPlatform] = useState<ContentPlatform>("youtube");
  const [url, setUrl] = useState("");
  const [resolved, setResolved] = useState<ResolvedCreator | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [channelId, setChannelId] = useState("");
  const [roleId, setRoleId] = useState("");
  const [styleId, setStyleId] = useState("");
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [liveMessage, setLiveMessage] = useState(DEFAULT_LIVE_MESSAGE);
  const [formError, setFormError] = useState<string | null>(null);
  const [previewPayload, setPreviewPayload] = useState<{
    content?: string;
    embeds?: DiscordWebhookEmbed[];
  } | null>(null);
  const [snapshot, setSnapshot] = useState("");
  const [resolving, setResolving] = useState(false);
  const resolveGeneration = useRef(0);

  const templateId = account?.template_id;
  const assignedTemplate = useMemo(() => {
    if (mode === "edit" && templateId) {
      return templates.find((t) => t.id === templateId) ?? null;
    }
    return templates.find((t) => t.platform_default_for === platform) ?? null;
  }, [mode, platform, templateId, templates]);

  const sharedTemplate = useMemo(() => {
    if (!assignedTemplate) return false;
    return accounts.filter((row) => row.template_id === assignedTemplate.id)
      .length > 1;
  }, [accounts, assignedTemplate]);

  const availableEvents = EVENT_TYPES_BY_PLATFORM[platform] ?? [
    "VIDEO_PUBLISHED",
  ];

  useEffect(() => {
    if (!visible) return;
    setFormError(null);
    setPreviewPayload(null);
    if (mode === "edit" && account) {
      const nextPlatform = account.source?.platform ?? "youtube";
      const nextUrl =
        account.source?.canonical_url || account.source?.profile_url || "";
      const nextEnabled = account.enabled;
      const nextChannel = account.destination_channel_id;
      const nextRole = account.ping_role_id ?? "";
      const nextStyle = account.sender_style_id ?? "";
      const nextEvents =
        account.event_types?.length > 0
          ? account.event_types
          : EVENT_TYPES_BY_PLATFORM[nextPlatform] ?? [];
      const template = templates.find((t) => t.id === account.template_id);
      const nextMessage = template?.content ?? DEFAULT_LIVE_MESSAGE;
      setPlatform(nextPlatform);
      setUrl(nextUrl);
      setResolved(null);
      setEnabled(nextEnabled);
      setChannelId(nextChannel);
      setRoleId(nextRole);
      setStyleId(nextStyle);
      setEventTypes(nextEvents);
      setLiveMessage(nextMessage);
      setSnapshot(
        JSON.stringify({
          enabled: nextEnabled,
          channelId: nextChannel,
          roleId: nextRole,
          styleId: nextStyle,
          eventTypes: nextEvents,
          liveMessage: nextMessage,
        })
      );
    } else {
      const defaults = EVENT_TYPES_BY_PLATFORM.youtube ?? [];
      setPlatform("youtube");
      setUrl("");
      setResolved(null);
      setEnabled(true);
      setChannelId("");
      setRoleId("");
      setStyleId("");
      setEventTypes(defaults);
      setLiveMessage(DEFAULT_LIVE_MESSAGE);
      setSnapshot("");
    }
  }, [account, mode, templates, visible]);

  const currentSnapshot = JSON.stringify({
    enabled,
    channelId,
    roleId,
    styleId,
    eventTypes,
    liveMessage,
  });
  const dirty =
    mode === "add"
      ? Boolean(url.trim() || channelId || liveMessage !== DEFAULT_LIVE_MESSAGE)
      : Boolean(snapshot) && currentSnapshot !== snapshot;

  const displayName =
    account?.source?.display_name ||
    account?.source?.username ||
    resolved?.display_name ||
    copy.unknownCreator;
  const title =
    mode === "edit"
      ? formatDict(copy.editAccount, { name: displayName })
      : copy.addAccount;

  function closeWithGuard() {
    if (!confirmDirtyClose(dirty, copy.unsavedConfirm)) return;
    onClose();
  }

  function toggleEvent(type: string, checked: boolean) {
    setEventTypes((current) => {
      if (checked) return current.includes(type) ? current : [...current, type];
      if (availableEvents.length <= 1) return current;
      return current.filter((item) => item !== type);
    });
  }

  async function handleResolve() {
    if (!url.trim() || resolving || saving) return;
    const generation = ++resolveGeneration.current;
    setFormError(null);
    setResolving(true);
    try {
      const creator = await resolveAccount(guildId, platform, url.trim());
      if (generation !== resolveGeneration.current) return;
      setResolved(creator);
      const template = templates.find((t) => t.platform_default_for === platform);
      if (template) setLiveMessage(template.content);
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/preview`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            platform,
            content: template?.content || liveMessage,
            ping_role_id: roleId || null,
          }),
        }
      );
      if (generation !== resolveGeneration.current) return;
      if (response.ok) {
        const data = await response.json();
        setPreviewPayload(data.payload);
      }
    } catch (err) {
      if (generation !== resolveGeneration.current) return;
      setFormError(mapResolveError(err, copy));
      setResolved(null);
    } finally {
      if (generation === resolveGeneration.current) setResolving(false);
    }
  }

  async function handleSave() {
    setFormError(null);
    if (!channelId || eventTypes.length === 0) {
      setFormError(copy.saveFailed);
      return;
    }
    try {
      if (mode === "add") {
        if (!url.trim()) {
          setFormError(copy.saveFailed);
          return;
        }
        let templateId: string | null = assignedTemplate?.id ?? null;
        if (!templateId) {
          const name = `${PLATFORM_LABELS[platform] ?? platform} ${copy.defaultTemplate}`;
          await createTemplate(guildId, {
            name,
            content: liveMessage,
            platform_default_for: platform,
          });
          const created = useContentNotificationsStore
            .getState()
            .templates.find(
              (t) => t.platform_default_for === platform && t.content === liveMessage
            );
          templateId = created?.id ?? null;
        } else if (assignedTemplate && assignedTemplate.content !== liveMessage) {
          await updateTemplate(guildId, assignedTemplate.id, {
            name: assignedTemplate.name,
            content: liveMessage,
            platform_default_for: assignedTemplate.platform_default_for,
            embed_json: assignedTemplate.embed_json,
          });
        }
        await createAccount(guildId, {
          platform,
          url: url.trim(),
          destination_channel_id: channelId,
          ping_role_id: roleId || null,
          template_id: templateId,
          sender_style_id: styleId || null,
          event_types: eventTypes,
          enabled,
        });
      } else if (account) {
        if (assignedTemplate && assignedTemplate.content !== liveMessage) {
          await updateTemplate(guildId, assignedTemplate.id, {
            name: assignedTemplate.name,
            content: liveMessage,
            platform_default_for: assignedTemplate.platform_default_for,
            embed_json: assignedTemplate.embed_json,
          });
        } else if (!assignedTemplate && liveMessage.trim()) {
          await createTemplate(guildId, {
            name: displayName,
            content: liveMessage,
            platform_default_for: platform,
          });
        }
        const nextTemplate =
          useContentNotificationsStore
            .getState()
            .templates.find((t) => t.id === account.template_id) ??
          useContentNotificationsStore
            .getState()
            .templates.find((t) => t.platform_default_for === platform);
        await updateAccount(guildId, account.id, {
          destination_channel_id: channelId,
          ping_role_id: roleId || null,
          template_id: nextTemplate?.id ?? account.template_id,
          sender_style_id: styleId || null,
          event_types: eventTypes,
          enabled,
        });
      }
      onClose();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : copy.saveFailed);
    }
  }

  const required = " *";

  return (
    <FeatureConfigurationModal
      visible={visible}
      title={title}
      category="messages"
      size="lg"
      saving={saving}
      error={formError}
      onClose={closeWithGuard}
      onSave={() => void handleSave()}
      saveDisabled={
        !channelId ||
        eventTypes.length === 0 ||
        (mode === "add" && !url.trim())
      }
    >
      <div className="d-flex flex-column gap-3">
        {mode === "edit" && account?.source ? (
          <div className="d-flex align-items-center gap-3">
            <PlatformAvatar
              src={account.source.avatar_url}
              displayName={displayName}
              platform={account.source.platform}
            />
            <div>
              <div className="fw-semibold">{displayName}</div>
              <div className="small text-body-secondary text-uppercase">
                {account.source.platform} · {account.source.username}
              </div>
            </div>
          </div>
        ) : null}

        {mode === "add" ? (
          <div>
            <label className="form-label small" htmlFor="cn-account-platform">
              {copy.platform}
              {required}
            </label>
            <CFormSelect
              id="cn-account-platform"
              value={platform}
              onChange={(e) => {
                const next = e.target.value as ContentPlatform;
                resolveGeneration.current += 1;
                setPlatform(next);
                setResolved(null);
                setResolving(false);
                setEventTypes(EVENT_TYPES_BY_PLATFORM[next] ?? []);
              }}
            >
              {(["youtube", "twitch", "kick", "x"] as const).map((id) => {
                const meta = platforms.find((p) => p.platform === id);
                const remaining =
                  id === "kick" ? meta?.total_remaining : meta?.active_remaining;
                const atLimit = typeof remaining === "number" && remaining <= 0;
                return (
                  <option
                    key={id}
                    value={id}
                    disabled={meta?.available === false || atLimit}
                  >
                    {PLATFORM_LABELS[id]}
                    {meta?.available === false
                      ? ` ${copy.unavailable}`
                      : atLimit
                        ? ` ${copy.limitReachedOption}`
                        : ""}
                  </option>
                );
              })}
            </CFormSelect>
            {platform === "kick" ? (
              <p className="small text-body-secondary mb-0 mt-2">
                {formatDict(copy.kickDisabledCount, {
                  limit: platforms.find((p) => p.platform === "kick")
                    ?.total_limit ?? 10,
                })}
              </p>
            ) : (
              <p className="small text-body-secondary mb-0 mt-2">
                {copy.disabledDoNotCount}
              </p>
            )}
          </div>
        ) : null}

        <div>
          <label className="form-label small" htmlFor="cn-account-url">
            {copy.accountUrl}
            {required}
          </label>
          {mode === "edit" ? (
            <CFormInput id="cn-account-url" value={url} readOnly />
          ) : (
            <div className="d-flex gap-2">
              <CFormInput
                id="cn-account-url"
                value={url}
                onChange={(e) => {
                  resolveGeneration.current += 1;
                  setUrl(e.target.value);
                  setResolved(null);
                  setResolving(false);
                }}
                placeholder="https://..."
              />
              <button
                type="button"
                className="btn btn-outline-light"
                disabled={saving || resolving || !url.trim()}
                onClick={() => void handleResolve()}
              >
                {copy.resolve}
              </button>
            </div>
          )}
        </div>

        {resolved ? (
          <div className="d-flex align-items-center gap-3 border rounded p-3">
            <PlatformAvatar
              src={resolved.avatar_url}
              displayName={resolved.display_name}
              platform={resolved.platform}
              size={48}
            />
            <div>
              <div className="fw-semibold">{resolved.display_name}</div>
              <div className="small text-body-secondary text-uppercase">
                {resolved.platform} · {resolved.username}
              </div>
            </div>
          </div>
        ) : null}

        {previewPayload ? (
          <div>
            <div className="small text-body-secondary mb-2">{copy.preview}</div>
            <MessagePreview
              content={previewPayload.content || ""}
              embed={webhookEmbedToPreview(previewPayload.embeds?.[0])}
              mode="embed"
              showContentWithEmbed
            />
          </div>
        ) : null}

        <div>
          <label className="form-label small" htmlFor="cn-account-status">
            {copy.accountStatus}
            {required}
          </label>
          <CFormSelect
            id="cn-account-status"
            value={enabled ? "enabled" : "paused"}
            onChange={(e) => setEnabled(e.target.value === "enabled")}
          >
            <option value="enabled">{copy.enabled}</option>
            <option value="paused">{copy.paused}</option>
          </CFormSelect>
        </div>

        <div>
          <ChannelPickerToolbar
            label={`${copy.discordChannel}${required}`}
            htmlFor="cn-account-channel"
          />
          <ChannelSelect
            id="cn-account-channel"
            channels={resources?.channels ?? []}
            value={channelId}
            onChange={setChannelId}
            allowEmpty
            emptyLabel={copy.discordChannel}
          />
        </div>

        <div>
          <RolePickerToolbar label={copy.pingRoleOptional} />
          <RoleSelect
            roles={resources?.roles ?? []}
            value={roleId}
            onChange={setRoleId}
            allowEmpty
            emptyLabel={copy.noneOption}
          />
        </div>

        <div>
          <label className="form-label small" htmlFor="cn-account-style">
            {copy.senderStyleOptional}
          </label>
          <CFormSelect
            id="cn-account-style"
            value={styleId}
            onChange={(e) => setStyleId(e.target.value)}
          >
            <option value="">{copy.defaultSender}</option>
            {styles.map((style) => (
              <option key={style.id} value={style.id}>
                {style.display_name}
              </option>
            ))}
          </CFormSelect>
          <p className="form-text mb-0">{copy.senderStyleMustSelect}</p>
        </div>

        <fieldset className="mb-0">
          <legend className="form-label small">
            {copy.contentType}
            {required}
          </legend>
          {availableEvents.map((type) => (
            <CFormCheck
              key={type}
              id={`cn-event-${type}`}
              label={localizeEventType(type, copy)}
              checked={eventTypes.includes(type)}
              onChange={(e) => toggleEvent(type, e.target.checked)}
            />
          ))}
        </fieldset>

        <div>
          <label className="form-label small" htmlFor="cn-live-message">
            {copy.liveMessage}
            {required}
          </label>
          <CFormTextarea
            id="cn-live-message"
            rows={5}
            value={liveMessage}
            onChange={(e) => setLiveMessage(e.target.value)}
          />
          <p className="form-text mb-0">{copy.liveMessageHelp}</p>
          {sharedTemplate ? (
            <p className="small text-warning mb-0 mt-2" role="status">
              {copy.templateSharedWarning}
            </p>
          ) : null}
        </div>
      </div>
    </FeatureConfigurationModal>
  );
}

function mapResolveError(
  err: unknown,
  copy: ContentNotificationsCopy,
): string {
  const code =
    err instanceof ContentNotificationApiError ? err.code : null;
  if (code === "invalid_url" || code === "not_found") {
    return copy.resolveInvalidAccount;
  }
  if (code === "platform_unavailable" || code === "auth_error") {
    return copy.resolveCredentialsMissing;
  }
  if (code === "rate_limited" || code === "quota_exhausted") {
    return copy.resolveRateLimited;
  }
  if (code === "platform_blocked") {
    return copy.resolveUnavailable;
  }
  return copy.resolveFailed;
}
