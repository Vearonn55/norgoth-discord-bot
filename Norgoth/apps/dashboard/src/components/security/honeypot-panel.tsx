"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  CAlert,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CSpinner,
} from "@coreui/react";
import { SectionCard } from "@/components/ui/section-card";
import { ChannelSelect } from "@/components/ui/channel-select";
import {
  ChannelPickerToolbar,
  RolePickerToolbar,
} from "@/components/ui/refresh-channels-button";
import { RoleSelect } from "@/components/ui/role-select";
import { MemberSelect } from "@/components/ui/member-select";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { NumberInput } from "@/components/ui/number-input";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { FeatureConfigurationModal } from "@/components/ui/feature-modal";
import { MutedSection } from "@/components/ui/feature-muting";
import { PageHeader } from "@/components/layout/page-header";
import { PageActionFooter } from "@/components/layout/page-action-footer";
import { EmbedEditor } from "@/components/discord/embed-editor";
import { EmbedWorkbench } from "@/components/discord/embed-workbench";
import { MessagePreview } from "@/components/discord/message-preview";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { EmbedDraftCreator } from "@/components/embed-messages/embed-draft-creator";
import { useFirstGuild } from "@/stores/guild-store";
import { useHoneypotStore, type HoneypotConfig } from "@/stores/honeypot-store";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";
import { Icon } from "@/components/ui/icon";
import { cilBan, cilBug, cilSettings, cilShieldAlt, cilWarning } from "@coreui/icons";
import type { DiscordEmbedPayload } from "@/lib/discord/message-payload";
import { useFeatureInfo } from "@/lib/feature-info";
import { formatDateTime } from "@/lib/datetime";
import {
  assertDiscordMarkdownLength,
  isBlankDiscordMarkdown,
} from "@/lib/discord-markdown-validation";
import { copyEmbedIntoHoneypot } from "@/lib/honeypot-embed-copy";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

type HoneypotFeature = "config" | "punishment" | "exemptions";
type EmbedSourceMode = "INLINE" | "SELECT_EXISTING" | "CREATE_NEW";

export function HoneypotPanel() {
  const dict = useLocaleDict();
  const d = dict.honeypotPage;
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId, resources, loading: guildLoading, error: guildError } = useFirstGuild();
  const config = useHoneypotStore((s) => s.config);
  const triggers = useHoneypotStore((s) => s.triggers);
  const loading = useHoneypotStore((s) => s.loading);
  const saving = useHoneypotStore((s) => s.saving);
  const error = useHoneypotStore((s) => s.error);
  const load = useHoneypotStore((s) => s.load);
  const save = useHoneypotStore((s) => s.save);
  const loadTriggers = useHoneypotStore((s) => s.loadTriggers);
  const embedMessages = useEmbedMessagesStore((s) => s.messages);
  const loadEmbedMessages = useEmbedMessagesStore((s) => s.load);
  const honeypotInfo = useFeatureInfo("honeypot");
  const [draft, setDraft] = useState<HoneypotConfig | null>(null);
  const [activeModal, setActiveModal] = useState<HoneypotFeature | null>(null);
  const [editorSeed, setEditorSeed] = useState(0);
  const [embedSourceMode, setEmbedSourceMode] =
    useState<EmbedSourceMode>("INLINE");
  const [creatorKey, setCreatorKey] = useState(0);
  const [draftSearch, setDraftSearch] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
    void loadTriggers(guildId);
    void loadEmbedMessages(guildId);
  }, [guildId, load, loadTriggers, loadEmbedMessages]);

  useEffect(() => {
    if (config) {
      setDraft(config);
      setEditorSeed((n) => n + 1);
    }
  }, [config]);

  const filteredDrafts = useMemo(() => {
    const q = draftSearch.trim().toLowerCase();
    if (!q) return embedMessages;
    return embedMessages.filter((m) => m.name.toLowerCase().includes(q));
  }, [embedMessages, draftSearch]);

  if (guildLoading || loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <CSpinner size="sm" /> {d.loading}
      </div>
    );
  }

  if (!guildId) {
    return <p className="text-body-secondary">{d.selectServer}</p>;
  }

  if (!draft) {
    return (
      <div className="d-flex flex-column gap-3">
        <CAlert color="danger" className="mb-0">
          {error || guildError || d.loadFailed}
        </CAlert>
        <div className="d-flex gap-2">
          <Button variant="secondary" onClick={() => void load(guildId)}>
            {d.retry}
          </Button>
        </div>
      </div>
    );
  }
  function patch(partial: Partial<HoneypotConfig>) {
    setDraft((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  function patchEmbedDescription(markdown: string) {
    const trimmed = isBlankDiscordMarkdown(markdown) ? "" : markdown;
    setDraft((prev) => {
      if (!prev) return prev;
      const base = (prev.warning_embed ?? {
        title: d.defaultEmbedTitle,
        description: "",
      }) as Record<string, unknown>;
      return {
        ...prev,
        warning_embed: { ...base, description: trimmed },
      };
    });
  }

  function applyEmbedCopy(message: EmbedMessage) {
    patch(copyEmbedIntoHoneypot(message));
    setEditorSeed((n) => n + 1);
    setEmbedSourceMode("INLINE");
  }

  // The master switch is authoritative and persists immediately so the
  // disabled state is saved even while the page-level Save is disabled.
  async function setEnabledAndSave(checked: boolean) {
    if (!draft) return;
    const next = { ...draft, enabled: checked };
    setDraft(next);
    if (guildId) await save(guildId, next);
  }

  async function saveDraft() {
    if (!guildId || !draft) return;
    setLocalError(null);
    const content = draft.warning_content ?? "";
    if (!isBlankDiscordMarkdown(content)) {
      const check = assertDiscordMarkdownLength(content, 2000);
      if (check.reason === "too_long") {
        setLocalError(d.warningContentTooLong);
        return;
      }
    }
    const desc = String(
      (draft.warning_embed as DiscordEmbedPayload | null)?.description ?? ""
    );
    if (!isBlankDiscordMarkdown(desc) && desc.trim().length > 4096) {
      setLocalError(d.embedDescriptionTooLong);
      return;
    }
    const normalized: HoneypotConfig = {
      ...draft,
      warning_content: isBlankDiscordMarkdown(content) ? "" : content.trim(),
      warning_embed: draft.warning_embed
        ? {
            ...draft.warning_embed,
            description: isBlankDiscordMarkdown(desc) ? "" : desc.trim(),
          }
        : null,
    };
    setDraft(normalized);
    await save(guildId, normalized);
  }

  async function handleModalSave() {
    if (!guildId || !draft) return;
    await save(guildId, draft);
    if (!useHoneypotStore.getState().error) setActiveModal(null);
  }

  const embed = (draft.warning_embed ?? {
    title: d.defaultEmbedTitle,
    description: "",
  }) as DiscordEmbedPayload;

  const dirty = JSON.stringify(draft) !== JSON.stringify(config);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={d.title}
        category="security"
        icon={<Icon icon={cilBug} size="xl" />}
        description={d.description}
        infoKey="honeypot"
        masterToggle={{
          enabled: draft.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
        }}
      />

      {config?.warning_status && config.warning_status.ok === false ? (
        <CAlert color="danger" className="mb-0">
          {config.warning_status.code === "pin_failed"
            ? d.warningPinFailed
            : config.warning_status.code === "missing_permissions"
              ? formatDict(d.warningPermissionError, {
                  permissions: (config.warning_status.missing ?? []).join(", ") ||
                    (config.warning_status.message ?? ""),
                })
              : d.warningDiscordUnavailable}
        </CAlert>
      ) : null}

      <CAlert
        color={draft.enabled ? "info" : "warning"}
        className="mb-0 d-flex align-items-start gap-2"
      >
        {!draft.enabled ? (
          <Icon icon={cilWarning} className="flex-shrink-0 mt-1" />
        ) : null}
        <span>
          {draft.enabled
            ? honeypotInfo?.alertActive
            : honeypotInfo?.alertInactive}
        </span>
      </CAlert>

      {error ? <p className="text-danger">{error}</p> : null}
      {localError ? <p className="text-danger">{localError}</p> : null}

      <MutedSection enabled={draft.enabled} className="d-flex flex-column gap-4">
        {/* Feature mini-cards */}
        <div className="row row-cols-1 row-cols-md-2 g-3">
          <div className="col">
            <MiniFeatureCard
              icon={cilSettings}
              name={d.configTitle}
              description={formatDict(d.configChannels, {
                count: draft.trap_channel_ids.length,
                plural:
                  draft.trap_channel_ids.length === 1
                    ? d.pluralEmpty
                    : d.pluralS,
              })}
              category="security"
              status="configured"
              onClick={() => setActiveModal("config")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilBan}
              name={d.punishmentTitle}
              description={formatDict(d.punishmentAction, {
                action: draft.punishment.replace(/_/g, " "),
              })}
              category="security"
              status="configured"
              onClick={() => setActiveModal("punishment")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilShieldAlt}
              name={d.exemptionsTitle}
              description={formatDict(d.exemptionsCardDesc, {
                roles: draft.exempt_role_ids.length,
                rolesPlural:
                  draft.exempt_role_ids.length === 1
                    ? d.pluralEmpty
                    : d.pluralS,
                members: draft.exempt_member_ids.length,
                membersPlural:
                  draft.exempt_member_ids.length === 1
                    ? d.pluralEmpty
                    : d.pluralS,
              })}
              category="security"
              enabled={draft.ignore_bots}
              onToggle={(checked) => patch({ ignore_bots: checked })}
              onClick={() => setActiveModal("exemptions")}
            />
          </div>
        </div>

        {/* Warning Message — TinyMCE + Embed Creator copy-into-snapshot */}
        <SectionCard level="primary" category="security" header={d.warningMessage}>
          <div className="d-flex flex-column gap-3 p-1">
            <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
              <div className="fw-medium">{d.postPinnedWarning}</div>
              <Switch
                checked={draft.post_pinned_warning}
                onChange={(checked) => patch({ post_pinned_warning: checked })}
                aria-label={d.postPinnedWarning}
              />
            </div>

            <div className="d-flex flex-wrap gap-2">
              <Button
                variant={embedSourceMode === "INLINE" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setEmbedSourceMode("INLINE")}
              >
                {d.editWarning}
              </Button>
              <Button
                variant={
                  embedSourceMode === "SELECT_EXISTING" ? "primary" : "secondary"
                }
                size="sm"
                onClick={() => setEmbedSourceMode("SELECT_EXISTING")}
              >
                {d.selectFromDraft}
              </Button>
              <Button
                variant={
                  embedSourceMode === "CREATE_NEW" ? "primary" : "secondary"
                }
                size="sm"
                onClick={() => {
                  setEmbedSourceMode("CREATE_NEW");
                  setCreatorKey((k) => k + 1);
                }}
              >
                {d.createNew}
              </Button>
            </div>

            {embedSourceMode === "SELECT_EXISTING" ? (
              <div className="d-flex flex-column gap-2">
                <p className="small text-body-secondary mb-0">
                  {d.copyDraftHelp}
                </p>
                <CFormInput
                  value={draftSearch}
                  onChange={(e) => setDraftSearch(e.target.value)}
                  placeholder={d.searchDrafts}
                  aria-label={d.searchDraftsAria}
                />
                <CFormSelect
                  value=""
                  aria-label={d.selectDraftAria}
                  onChange={(event) => {
                    const id = event.target.value;
                    if (!id) return;
                    const message = embedMessages.find((m) => m.id === id);
                    if (message) applyEmbedCopy(message);
                  }}
                >
                  <option value="">{d.selectDraft}</option>
                  {filteredDrafts.map((message) => (
                    <option key={message.id} value={message.id}>
                      {message.name}
                    </option>
                  ))}
                </CFormSelect>
              </div>
            ) : null}

            {embedSourceMode === "CREATE_NEW" ? (
              <EmbedDraftCreator
                key={`honeypot-create-${creatorKey}`}
                guildId={guildId}
                compact
                onCreated={(message) => {
                  applyEmbedCopy(message);
                  void loadEmbedMessages(guildId);
                }}
                onCancel={() => setEmbedSourceMode("INLINE")}
              />
            ) : null}

            {embedSourceMode === "INLINE" ? (
              <EmbedWorkbench
                editor={
                  <div className="d-flex flex-column gap-3">
                    <div>
                      <CFormLabel>{d.content}</CFormLabel>
                      <RichMessageEditor
                        key={`honeypot-content-${editorSeed}`}
                        value={draft.warning_content}
                        onChange={(markdown) =>
                          patch({
                            warning_content: isBlankDiscordMarkdown(markdown)
                              ? ""
                              : markdown,
                          })
                        }
                        height={180}
                        placeholder={d.contentPlaceholder}
                      />
                      <p className="mt-1 mb-0 small text-body-secondary">
                        {formatDict(d.charCount, {
                          count: draft.warning_content.length,
                        })}
                      </p>
                    </div>
                    <div>
                      <CFormLabel>{d.embedDescription}</CFormLabel>
                      <RichMessageEditor
                        key={`honeypot-desc-${editorSeed}`}
                        value={String(embed.description ?? "")}
                        onChange={patchEmbedDescription}
                        height={180}
                        placeholder={d.embedDescriptionPlaceholder}
                      />
                    </div>
                    <EmbedEditor
                      value={embed}
                      guildId={guildId ?? undefined}
                      hideDescription
                      onChange={(next) =>
                        patch({ warning_embed: next as Record<string, unknown> })
                      }
                    />
                  </div>
                }
                preview={
                  <MessagePreview
                    content={draft.warning_content}
                    embed={embed}
                    mode="embed"
                    showContentWithEmbed
                    showImagePlaceholders
                  />
                }
              />
            ) : null}
          </div>
        </SectionCard>
      </MutedSection>

      {/* Configuration modal */}
      <FeatureConfigurationModal
        visible={activeModal === "config"}
        title={d.configTitle}
        category="security"
        icon={cilSettings}
        saving={saving}
        error={error}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <CAlert color="secondary" className="mb-0 py-2 small">
            {d.configToggleHint}
          </CAlert>
          <div>
            <ChannelPickerToolbar label={d.trapChannels} />
            <CAlert color="warning" className="py-2 small">
              {d.trapChannelsWarn}
            </CAlert>
            <ChannelSelect
              channels={resources?.channels ?? []}
              value=""
              allowEmpty
              emptyLabel={d.addTrapChannel}
              onChange={(id) => {
                if (!id || draft.trap_channel_ids.includes(id)) return;
                patch({ trap_channel_ids: [...draft.trap_channel_ids, id] });
              }}
            />
            <ul className="small mt-2 mb-0">
              {draft.trap_channel_ids.map((id) => {
                const ch = resources?.channels.find((c) => c.id === id);
                return (
                  <li key={id}>
                    #{ch?.name ?? dict.common.channelUnavailable}{" "}
                    <button
                      type="button"
                      className="btn btn-link btn-sm p-0"
                      onClick={() =>
                        patch({
                          trap_channel_ids: draft.trap_channel_ids.filter(
                            (x) => x !== id
                          ),
                        })
                      }
                    >
                      {d.remove}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </FeatureConfigurationModal>

      {/* Punishment modal */}
      <FeatureConfigurationModal
        visible={activeModal === "punishment"}
        title={d.punishmentTitle}
        category="security"
        icon={cilBan}
        saving={saving}
        error={error}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <div>
            <CFormLabel>{d.action}</CFormLabel>
            <CFormSelect
              value={draft.punishment}
              onChange={(e) =>
                patch({
                  punishment: e.target.value as HoneypotConfig["punishment"],
                })
              }
            >
              <option value="log_only">{d.punishmentLogOnly}</option>
              <option value="delete">{d.punishmentDelete}</option>
              <option value="timeout">{d.punishmentTimeout}</option>
              <option value="kick">{d.punishmentKick}</option>
              <option value="kick_purge">{d.punishmentKickPurge}</option>
              <option value="ban">{d.punishmentBan}</option>
            </CFormSelect>
          </div>
          <div>
            <CFormLabel>{d.deleteHistoryHours}</CFormLabel>
            <NumberInput
              value={draft.delete_history_hours}
              defaultValue={0}
              min={0}
              max={24}
              step={1}
              aria-label={d.deleteHistoryAria}
              onCommit={(next) => patch({ delete_history_hours: next })}
            />
          </div>
          <div>
            <CFormLabel>{d.timeoutMinutes}</CFormLabel>
            <NumberInput
              value={draft.timeout_minutes}
              defaultValue={10}
              min={1}
              max={40320}
              step={1}
              aria-label={d.timeoutMinutesAria}
              onCommit={(next) => patch({ timeout_minutes: next })}
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      {/* Exemptions modal */}
      <FeatureConfigurationModal
        visible={activeModal === "exemptions"}
        title={d.exemptionsTitle}
        category="security"
        icon={cilShieldAlt}
        saving={saving}
        error={error}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <CAlert color="secondary" className="mb-0 py-2 small">
            {d.exemptionsHint}
          </CAlert>
          <div>
            <RolePickerToolbar label={d.exemptRoles} />
            <RoleSelect
              roles={resources?.roles ?? []}
              value=""
              onChange={() => undefined}
              multiple
              values={draft.exempt_role_ids}
              onChangeMultiple={(ids) => patch({ exempt_role_ids: ids })}
            />
          </div>
          <div>
            <CFormLabel>{d.exemptMembers}</CFormLabel>
            <MemberSelect
              guildId={guildId}
              values={draft.exempt_member_ids}
              onChange={(ids) => patch({ exempt_member_ids: ids })}
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      <SectionCard level="secondary" header={d.triggerHistory}>
        {triggers.length === 0 ? (
          <p className="mb-0 small text-body-secondary p-1">
            {d.emptyTriggers}
          </p>
        ) : (
          <div className="table-responsive">
            <table className="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>{d.colWhen}</th>
                  <th>{d.colMember}</th>
                  <th>{d.colChannel}</th>
                  <th>{d.colPunishment}</th>
                  <th>{d.colResult}</th>
                </tr>
              </thead>
              <tbody>
                {triggers.map((item, index) => (
                  <tr key={String(item.id ?? index)}>
                    <td className="small">
                      {formatDateTime(
                        String(item.triggered_at ?? item.created_at ?? ""),
                        lang
                      )}
                    </td>
                    <td className="small">
                      {String(
                        item.username ?? item.user_id ?? item.display_name ?? "—"
                      )}
                    </td>
                    <td className="small">{String(item.channel_id ?? "—")}</td>
                    <td className="small">{String(item.punishment ?? "—")}</td>
                    <td className="small">
                      {String(item.punishment_status ?? item.result ?? "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <PageActionFooter>
        <Button
          variant="primary"
          disabled={saving || !draft.enabled || !dirty}
          onClick={() => void saveDraft()}
        >
          {saving ? d.saving : d.saveSettings}
        </Button>
      </PageActionFooter>
    </div>
  );
}



