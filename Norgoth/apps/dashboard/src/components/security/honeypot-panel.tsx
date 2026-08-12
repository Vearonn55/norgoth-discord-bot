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

type HoneypotFeature = "config" | "punishment" | "exemptions";
type EmbedSourceMode = "INLINE" | "SELECT_EXISTING" | "CREATE_NEW";

export function HoneypotPanel() {
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
  const requestCreateChannel = useHoneypotStore((s) => s.requestCreateChannel);
  const embedMessages = useEmbedMessagesStore((s) => s.messages);
  const loadEmbedMessages = useEmbedMessagesStore((s) => s.load);
  const honeypotInfo = useFeatureInfo("honeypot");
  const [draft, setDraft] = useState<HoneypotConfig | null>(null);
  const [newChannelName, setNewChannelName] = useState("honeypot");
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
        <CSpinner size="sm" /> Loading honeypot...
      </div>
    );
  }

  if (!guildId) {
    return <p className="text-body-secondary">Select a server first.</p>;
  }

  if (!draft) {
    return (
      <div className="d-flex flex-column gap-3">
        <CAlert color="danger" className="mb-0">
          {error || guildError || "Honeypot configuration could not be loaded."}
        </CAlert>
        <div className="d-flex gap-2">
          <Button variant="secondary" onClick={() => void load(guildId)}>
            Retry
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
        title: "Honeypot Channel",
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
        setLocalError("Warning content must be 2000 characters or fewer.");
        return;
      }
    }
    const desc = String(
      (draft.warning_embed as DiscordEmbedPayload | null)?.description ?? ""
    );
    if (!isBlankDiscordMarkdown(desc) && desc.trim().length > 4096) {
      setLocalError("Embed description must be 4096 characters or fewer.");
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
    title: "Honeypot Channel",
    description: "",
  }) as DiscordEmbedPayload;

  const dirty = JSON.stringify(draft) !== JSON.stringify(config);

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title="Honeypot"
        category="security"
        icon={<Icon icon={cilBug} size="xl" />}
        description="Trap channels that catch spam bots posting indiscriminately across every visible channel."
        infoKey="honeypot"
        masterToggle={{
          enabled: draft.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
        }}
      />

      <CAlert
        color={draft.enabled ? "info" : "warning"}
        className="mb-0 d-flex align-items-start gap-2"
      >
        {!draft.enabled ? (
          <Icon icon={cilWarning} className="flex-shrink-0 mt-1" />
        ) : null}
        <span>
          {draft.enabled
            ? honeypotInfo?.alertActive ||
              "The honeypot is active. Legitimate members must be warned never to use the trap channel."
            : honeypotInfo?.alertInactive ||
              "The honeypot trap is currently inactive. Enable it from the header to start catching spam bots."}
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
              name="Configuration"
              description={`${draft.trap_channel_ids.length} trap channel${draft.trap_channel_ids.length === 1 ? "" : "s"}`}
              category="security"
              status="configured"
              onClick={() => setActiveModal("config")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilBan}
              name="Punishment"
              description={`Action: ${draft.punishment.replace(/_/g, " ")}`}
              category="security"
              status="configured"
              onClick={() => setActiveModal("punishment")}
            />
          </div>
          <div className="col">
            <MiniFeatureCard
              icon={cilShieldAlt}
              name="Exemptions"
              description={`Ignore bots • ${draft.exempt_role_ids.length} role${draft.exempt_role_ids.length === 1 ? "" : "s"}, ${draft.exempt_member_ids.length} member${draft.exempt_member_ids.length === 1 ? "" : "s"}`}
              category="security"
              enabled={draft.ignore_bots}
              onToggle={(checked) => patch({ ignore_bots: checked })}
              onClick={() => setActiveModal("exemptions")}
            />
          </div>
        </div>

        {/* Warning Message — TinyMCE + Embed Creator copy-into-snapshot */}
        <SectionCard level="primary" category="security" header="Warning Message">
          <div className="d-flex flex-column gap-3 p-1">
            <div className="d-flex align-items-center justify-content-between gap-3 border rounded p-3">
              <div className="fw-medium">Post a pinned warning</div>
              <Switch
                checked={draft.post_pinned_warning}
                onChange={(checked) => patch({ post_pinned_warning: checked })}
                aria-label="Post a pinned warning"
              />
            </div>

            <div className="d-flex flex-wrap gap-2">
              <Button
                variant={embedSourceMode === "INLINE" ? "primary" : "secondary"}
                size="sm"
                onClick={() => setEmbedSourceMode("INLINE")}
              >
                Edit Warning
              </Button>
              <Button
                variant={
                  embedSourceMode === "SELECT_EXISTING" ? "primary" : "secondary"
                }
                size="sm"
                onClick={() => setEmbedSourceMode("SELECT_EXISTING")}
              >
                Select From Draft
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
                Create New
              </Button>
            </div>

            {embedSourceMode === "SELECT_EXISTING" ? (
              <div className="d-flex flex-column gap-2">
                <p className="small text-body-secondary mb-0">
                  Copy an Embed Library draft into this honeypot warning. Editing
                  the warning afterward does not change the library draft.
                </p>
                <CFormInput
                  value={draftSearch}
                  onChange={(e) => setDraftSearch(e.target.value)}
                  placeholder="Search drafts…"
                  aria-label="Search Embed Library drafts"
                />
                <CFormSelect
                  value=""
                  aria-label="Select Embed Library draft"
                  onChange={(event) => {
                    const id = event.target.value;
                    if (!id) return;
                    const message = embedMessages.find((m) => m.id === id);
                    if (message) applyEmbedCopy(message);
                  }}
                >
                  <option value="">Select a draft to copy…</option>
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
                      <CFormLabel>Content</CFormLabel>
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
                        placeholder="Message above the warning embed…"
                      />
                      <p className="mt-1 mb-0 small text-body-secondary">
                        {draft.warning_content.length}/2000 characters
                      </p>
                    </div>
                    <div>
                      <CFormLabel>Embed Description</CFormLabel>
                      <RichMessageEditor
                        key={`honeypot-desc-${editorSeed}`}
                        value={String(embed.description ?? "")}
                        onChange={patchEmbedDescription}
                        height={180}
                        placeholder="Embed description…"
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
        title="Configuration"
        category="security"
        icon={cilSettings}
        saving={saving}
        error={error}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <CAlert color="secondary" className="mb-0 py-2 small">
            Enable or disable the honeypot from the Configuration card toggle.
          </CAlert>
          <div>
            <CFormLabel>Trap Channels</CFormLabel>
            <CAlert color="warning" className="py-2 small">
              Selecting an existing channel turns it into a trap. Do not choose
              an active conversation channel.
            </CAlert>
            <ChannelSelect
              channels={resources?.channels ?? []}
              value=""
              allowEmpty
              emptyLabel="Add trap channel…"
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
                    #{ch?.name ?? id}{" "}
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
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="d-flex gap-2 align-items-end">
            <div className="flex-grow-1">
              <CFormLabel>Create Honeypot Channel</CFormLabel>
              <CFormInput
                value={newChannelName}
                onChange={(e) => setNewChannelName(e.target.value)}
              />
            </div>
            <Button
              variant="secondary"
              onClick={() =>
                void requestCreateChannel(guildId, newChannelName).then(() =>
                  load(guildId)
                )
              }
            >
              Create
            </Button>
          </div>
        </div>
      </FeatureConfigurationModal>

      {/* Punishment modal */}
      <FeatureConfigurationModal
        visible={activeModal === "punishment"}
        title="Punishment"
        category="security"
        icon={cilBan}
        saving={saving}
        error={error}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <div>
            <CFormLabel>Action</CFormLabel>
            <CFormSelect
              value={draft.punishment}
              onChange={(e) =>
                patch({
                  punishment: e.target.value as HoneypotConfig["punishment"],
                })
              }
            >
              <option value="log_only">Log Only</option>
              <option value="delete">Delete Trigger Message</option>
              <option value="timeout">Timeout Member</option>
              <option value="kick">Kick Member</option>
              <option value="kick_purge">Kick + Purge Recent Messages</option>
              <option value="ban">Ban Member</option>
            </CFormSelect>
          </div>
          <div>
            <CFormLabel>Delete Message History (Hours, max 24)</CFormLabel>
            <NumberInput
              value={draft.delete_history_hours}
              defaultValue={0}
              min={0}
              max={24}
              step={1}
              aria-label="Delete message history hours"
              onCommit={(next) => patch({ delete_history_hours: next })}
            />
          </div>
          <div>
            <CFormLabel>Timeout Minutes</CFormLabel>
            <NumberInput
              value={draft.timeout_minutes}
              defaultValue={10}
              min={1}
              max={40320}
              step={1}
              aria-label="Timeout minutes"
              onCommit={(next) => patch({ timeout_minutes: next })}
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      {/* Exemptions modal */}
      <FeatureConfigurationModal
        visible={activeModal === "exemptions"}
        title="Exemptions"
        category="security"
        icon={cilShieldAlt}
        saving={saving}
        error={error}
        onClose={() => setActiveModal(null)}
        onSave={handleModalSave}
      >
        <div className="d-flex flex-column gap-3">
          <CAlert color="secondary" className="mb-0 py-2 small">
            Toggle “Ignore bots” from the Exemptions card. Configure exempt roles
            and members below.
          </CAlert>
          <div>
            <CFormLabel>Exempt Roles</CFormLabel>
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
            <CFormLabel>Exempt Members</CFormLabel>
            <MemberSelect
              guildId={guildId}
              values={draft.exempt_member_ids}
              onChange={(ids) => patch({ exempt_member_ids: ids })}
            />
          </div>
        </div>
      </FeatureConfigurationModal>

      <SectionCard level="secondary" header="Trigger History">
        {triggers.length === 0 ? (
          <p className="mb-0 small text-body-secondary p-1">
            No honeypot triggers yet.
          </p>
        ) : (
          <div className="table-responsive">
            <table className="table table-sm align-middle mb-0">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Member</th>
                  <th>Channel</th>
                  <th>Punishment</th>
                  <th>Result</th>
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
          {saving ? "Saving…" : "Save Settings"}
        </Button>
      </PageActionFooter>
    </div>
  );
}



