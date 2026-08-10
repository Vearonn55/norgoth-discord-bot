"use client";

import { useEffect, useState } from "react";
import {
  CAlert,
  CCol,
  CFormLabel,
  CFormSelect,
  CModal,
  CModalBody,
  CModalHeader,
  CModalTitle,
  CRow,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { RoleMultiPicker } from "@/components/ui/role-multi-picker";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { MessagePreview } from "@/components/discord/message-preview";
import { EmbedDraftCreator } from "@/components/embed-messages/embed-draft-creator";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useAutomationStore,
  type AutomationConfig,
  type MessageSource,
} from "@/stores/automation-store";
import {
  useEmbedMessagesStore,
  type EmbedMessage,
} from "@/stores/embed-messages-store";

type Section = "welcome" | "autorole" | "modlog";

const WELCOME_VARIABLES = [
  "{user}",
  "{username}",
  "{server}",
  "{member_count}",
  "{inviter}",
  "{inviter_count}",
];

export function AutomationSettingsPanel({ section }: { section: Section }) {
  const { guildId, resources, loading: guildLoading, error: guildError, reload } =
    useFirstGuild();

  const config = useAutomationStore((s) => s.config);
  const savedConfig = useAutomationStore((s) => s.savedConfig);
  const welcomeStatus = useAutomationStore((s) => s.welcomeStatus);
  const autoroleStatus = useAutomationStore((s) => s.autoroleStatus);
  const loading = useAutomationStore((s) => s.loading);
  const saving = useAutomationStore((s) => s.saving);
  const savingSection = useAutomationStore((s) => s.savingSection);
  const testing = useAutomationStore((s) => s.testing);
  const dirty = useAutomationStore((s) => s.dirty);
  const editorSeed = useAutomationStore((s) => s.editorSeed);
  const error = useAutomationStore((s) => s.error);
  const savedAt = useAutomationStore((s) => s.savedAt);
  const welcomeSavedAt = useAutomationStore((s) => s.welcomeSavedAt);
  const welcomeError = useAutomationStore((s) => s.welcomeError);
  const leaveSavedAt = useAutomationStore((s) => s.leaveSavedAt);
  const leaveError = useAutomationStore((s) => s.leaveError);
  const testResult = useAutomationStore((s) => s.testResult);
  const testError = useAutomationStore((s) => s.testError);
  const leaveTesting = useAutomationStore((s) => s.leaveTesting);
  const leaveTestResult = useAutomationStore((s) => s.leaveTestResult);
  const leaveTestError = useAutomationStore((s) => s.leaveTestError);
  const updateConfig = useAutomationStore((s) => s.updateConfig);
  const load = useAutomationStore((s) => s.load);
  const save = useAutomationStore((s) => s.save);
  const saveSection = useAutomationStore((s) => s.saveSection);
  const sendTestWelcome = useAutomationStore((s) => s.sendTestWelcome);
  const sendTestLeave = useAutomationStore((s) => s.sendTestLeave);

  const embedMessages = useEmbedMessagesStore((s) => s.messages);
  const loadEmbedMessages = useEmbedMessagesStore((s) => s.load);
  const [creatorFor, setCreatorFor] = useState<"welcome" | "leave" | null>(
    null
  );

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  useEffect(() => {
    if (!guildId || section !== "welcome") return;
    void loadEmbedMessages(guildId);
  }, [guildId, section, loadEmbedMessages]);

  if (guildLoading || loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          <span>Loading automation settings…</span>
        </div>
      </Card>
    );
  }

  if (guildError || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="mb-0 text-body-secondary">{guildError}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);

  const welcomeMisconfigured =
    config.welcome_enabled && !config.welcome_channel_id;
  const leaveMisconfigured =
    config.leave_enabled &&
    !config.leave_channel_id &&
    !config.welcome_channel_id;

  const welcomeDirty =
    config.welcome_enabled !== savedConfig.welcome_enabled ||
    config.welcome_channel_id !== savedConfig.welcome_channel_id ||
    config.welcome_message !== savedConfig.welcome_message ||
    config.welcome_source !== savedConfig.welcome_source ||
    config.welcome_embed_message_id !== savedConfig.welcome_embed_message_id;
  const leaveDirty =
    config.leave_enabled !== savedConfig.leave_enabled ||
    config.leave_channel_id !== savedConfig.leave_channel_id ||
    config.leave_message !== savedConfig.leave_message ||
    config.leave_source !== savedConfig.leave_source ||
    config.leave_embed_message_id !== savedConfig.leave_embed_message_id;

  const previewSubstitute = (text: string) =>
    text
      .replaceAll("{user}", "@Member")
      .replaceAll("{username}", "Member")
      .replaceAll("{server}", resources?.guild_name ?? "Server")
      .replaceAll("{member_count}", "1,234")
      .replaceAll("{inviter}", "@Inviter")
      .replaceAll("{inviter_count}", "42");

  return (
    <div className="d-flex flex-column gap-3">
      {resources && (
        <div className="d-flex align-items-center gap-2">
          <Badge variant="success">{resources.guild_name}</Badge>
          <span className="small text-body-secondary">
            Guild ID: {resources.guild_id}
          </span>
        </div>
      )}

      {section === "welcome" && (
        <div className="row g-4">
          {/* Welcome card */}
          <div className="col-12 col-xl-6">
            <Card className="h-100">
              <div className="d-flex flex-column gap-3 h-100">
                <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
                  <h2 className="h5 mb-0">Welcome Message</h2>
                  <Badge variant={config.welcome_enabled ? "success" : "neutral"}>
                    {config.welcome_enabled ? "On" : "Off"}
                  </Badge>
                </div>

                <ToggleRow
                  label="Welcome messages"
                  description="Announce joins in a channel."
                  checked={config.welcome_enabled}
                  onChange={(checked) =>
                    updateConfig((current) => ({
                      ...current,
                      welcome_enabled: checked,
                    }))
                  }
                />

                {welcomeMisconfigured ? (
                  <CAlert color="warning" className="mb-0 py-2">
                    Enabled but no channel selected — nothing will send until you
                    pick one and save.
                  </CAlert>
                ) : null}

                <SelectRow
                  label="Welcome channel"
                  value={config.welcome_channel_id ?? ""}
                  onChange={(value) =>
                    updateConfig((current) => ({
                      ...current,
                      welcome_channel_id: value || null,
                    }))
                  }
                  options={channels.map((channel) => ({
                    value: channel.id,
                    label: `#${channel.name}`,
                  }))}
                  placeholder="Select a channel"
                />

                <MessageComposer
                  section="welcome"
                  label="Welcome message"
                  placeholder="Welcome to {server}, {user}!"
                  config={config}
                  updateConfig={updateConfig}
                  editorSeed={editorSeed}
                  embedMessages={embedMessages}
                  previewSubstitute={previewSubstitute}
                  onCreateNew={() => setCreatorFor("welcome")}
                />

                {welcomeStatus ? (
                  <CAlert
                    color={welcomeStatus.ok ? "success" : "danger"}
                    className="mb-0 py-2"
                  >
                    Last attempt: {welcomeStatus.ok ? "delivered" : "failed"}
                    {" — "}
                    {welcomeStatus.reason}
                  </CAlert>
                ) : null}

                <div className="mt-auto">
                  <hr className="norgoth-divider-strong my-1" />

                  <div className="d-flex flex-wrap align-items-center gap-3">
                    <Button
                      variant="primary"
                      onClick={() => void saveSection(guildId, "welcome")}
                      disabled={saving && savingSection === "welcome"}
                    >
                      {saving && savingSection === "welcome"
                        ? "Saving…"
                        : "Save Welcome"}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void sendTestWelcome(guildId)}
                      disabled={testing || !config.welcome_channel_id}
                    >
                      {testing ? "Saving & sending…" : "Test Message"}
                    </Button>
                    {welcomeDirty ? (
                      <span className="small text-warning">Unsaved changes</span>
                    ) : welcomeSavedAt ? (
                      <span className="small text-success">Saved</span>
                    ) : null}
                    {welcomeError ? (
                      <span className="small text-danger">{welcomeError}</span>
                    ) : null}
                    {testResult ? (
                      <span className="small text-success">{testResult}</span>
                    ) : null}
                    {testError ? (
                      <span className="small text-danger">{testError}</span>
                    ) : null}
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Leave card */}
          <div className="col-12 col-xl-6">
            <Card className="h-100">
              <div className="d-flex flex-column gap-3 h-100">
                <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
                  <h2 className="h5 mb-0">Leave Message</h2>
                  <Badge variant={config.leave_enabled ? "success" : "neutral"}>
                    {config.leave_enabled ? "On" : "Off"}
                  </Badge>
                </div>

                <ToggleRow
                  label="Leave messages"
                  description="Announce when members leave."
                  checked={config.leave_enabled}
                  onChange={(checked) =>
                    updateConfig((current) => ({
                      ...current,
                      leave_enabled: checked,
                    }))
                  }
                />

                {leaveMisconfigured ? (
                  <CAlert color="warning" className="mb-0 py-2">
                    Enabled but no leave/welcome channel selected.
                  </CAlert>
                ) : null}

                <SelectRow
                  label="Leave channel"
                  value={config.leave_channel_id ?? ""}
                  onChange={(value) =>
                    updateConfig((current) => ({
                      ...current,
                      leave_channel_id: value || null,
                    }))
                  }
                  options={channels.map((channel) => ({
                    value: channel.id,
                    label: `#${channel.name}`,
                  }))}
                  placeholder="Same as welcome channel"
                />

                <MessageComposer
                  section="leave"
                  label="Leave message"
                  placeholder="{username} left {server}."
                  config={config}
                  updateConfig={updateConfig}
                  editorSeed={editorSeed}
                  embedMessages={embedMessages}
                  previewSubstitute={previewSubstitute}
                  onCreateNew={() => setCreatorFor("leave")}
                />

                <div className="mt-auto">
                  <hr className="norgoth-divider-strong my-1" />

                  <div className="d-flex flex-wrap align-items-center gap-3">
                    <Button
                      variant="primary"
                      onClick={() => void saveSection(guildId, "leave")}
                      disabled={saving && savingSection === "leave"}
                    >
                      {saving && savingSection === "leave"
                        ? "Saving…"
                        : "Save Leave"}
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void sendTestLeave(guildId)}
                      disabled={
                        leaveTesting ||
                        (!config.leave_channel_id && !config.welcome_channel_id)
                      }
                    >
                      {leaveTesting ? "Saving & sending…" : "Test Message"}
                    </Button>
                    {leaveDirty ? (
                      <span className="small text-warning">Unsaved changes</span>
                    ) : leaveSavedAt ? (
                      <span className="small text-success">Saved</span>
                    ) : null}
                    {leaveError ? (
                      <span className="small text-danger">{leaveError}</span>
                    ) : null}
                    {leaveTestResult ? (
                      <span className="small text-success">
                        {leaveTestResult}
                      </span>
                    ) : null}
                    {leaveTestError ? (
                      <span className="small text-danger">{leaveTestError}</span>
                    ) : null}
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {section === "welcome" && creatorFor ? (
        <CModal
          size="xl"
          visible
          onClose={() => setCreatorFor(null)}
          alignment="center"
        >
          <CModalHeader>
            <CModalTitle>Create embed draft</CModalTitle>
          </CModalHeader>
          <CModalBody>
            <EmbedDraftCreator
              guildId={guildId}
              channels={channels}
              mode="create"
              compact
              onCancel={() => setCreatorFor(null)}
              cancelLabel="Cancel"
              onCreated={(created) => {
                const target = creatorFor;
                setCreatorFor(null);
                if (guildId) void loadEmbedMessages(guildId);
                updateConfig((current) =>
                  target === "welcome"
                    ? {
                        ...current,
                        welcome_source: "embed",
                        welcome_embed_message_id: created.id,
                      }
                    : {
                        ...current,
                        leave_source: "embed",
                        leave_embed_message_id: created.id,
                      }
                );
              }}
            />
          </CModalBody>
        </CModal>
      ) : null}

      {section === "autorole" && (
        <CRow className="g-3">
          <CCol xl={8} lg={10}>
            <Card>
              <div className="d-flex flex-column gap-3">
                <div className="d-flex flex-wrap align-items-start justify-content-between gap-3">
                  <div className="min-w-0">
                    <h2 className="h5 mb-1">Auto-role on join</h2>
                    <p className="mb-0 small text-body-secondary">
                      Grant one or more roles to every new member. Enable both
                      this switch and the Auto Role module. The bot role must
                      sit above these roles in Discord (Manage Roles).
                    </p>
                  </div>
                  <div className="d-flex align-items-center gap-2">
                    <Badge
                      variant={
                        config.auto_role_enabled ? "success" : "neutral"
                      }
                    >
                      {config.auto_role_enabled ? "Enabled" : "Disabled"}
                    </Badge>
                    <Switch
                      checked={config.auto_role_enabled}
                      onChange={(checked) =>
                        updateConfig((current) => ({
                          ...current,
                          auto_role_enabled: checked,
                        }))
                      }
                      aria-label="Auto-role on join"
                    />
                  </div>
                </div>

                <RoleMultiPicker
                  roles={roles}
                  selectedIds={
                    config.auto_role_ids?.length
                      ? config.auto_role_ids
                      : config.auto_role_id
                        ? [config.auto_role_id]
                        : []
                  }
                  onChange={(ids) =>
                    updateConfig((current) => ({
                      ...current,
                      auto_role_ids: ids,
                      auto_role_id: ids[0] ?? null,
                    }))
                  }
                  searchPlaceholder="Search roles to grant…"
                />

                {autoroleStatus ? (
                  <CAlert
                    color={autoroleStatus.ok ? "success" : "warning"}
                    className="mb-0 py-2"
                  >
                    <strong>
                      {autoroleStatus.ok
                        ? "Last assignment succeeded"
                        : "Last assignment issue"}
                    </strong>
                    : {autoroleStatus.reason}
                    {autoroleStatus.member_name
                      ? ` (${autoroleStatus.member_name})`
                      : ""}
                  </CAlert>
                ) : null}
              </div>
            </Card>
          </CCol>
        </CRow>
      )}

      {section === "modlog" && (
        <CRow className="g-3">
          <CCol md={8} xl={6}>
            <Card>
              <div className="d-flex flex-column gap-2">
                <h2 className="h6 mb-0">Moderation log channel</h2>
                <p className="mb-0 small text-body-secondary">
                  Kick, ban, timeout, and purge actions post embeds here.
                </p>
                <CFormSelect
                  value={config.mod_log_channel_id ?? ""}
                  onChange={(event) =>
                    updateConfig((current) => ({
                      ...current,
                      mod_log_channel_id: event.target.value || null,
                    }))
                  }
                >
                  <option value="">Select a channel</option>
                  {channels.map((channel) => (
                    <option key={channel.id} value={channel.id}>
                      #{channel.name}
                    </option>
                  ))}
                </CFormSelect>
              </div>
            </Card>
          </CCol>
        </CRow>
      )}

      {section !== "welcome" ? (
        <div className="d-flex flex-wrap align-items-center gap-3">
          <Button
            variant="primary"
            onClick={() => void save(guildId)}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save Settings"}
          </Button>

          {dirty ? (
            <CAlert color="warning" className="mb-0 py-2">
              Unsaved changes — settings use the last saved values.
            </CAlert>
          ) : null}

          {savedAt && !dirty ? (
            <span className="small text-success">Saved at {savedAt}</span>
          ) : null}
        </div>
      ) : null}

      {error && (
        <CAlert color="danger" className="mb-0 py-2">
          {error}
        </CAlert>
      )}
    </div>
  );
}

function MessageComposer({
  section,
  label,
  placeholder,
  config,
  updateConfig,
  editorSeed,
  embedMessages,
  previewSubstitute,
  onCreateNew,
}: {
  section: "welcome" | "leave";
  label: string;
  placeholder: string;
  config: AutomationConfig;
  updateConfig: (updater: (current: AutomationConfig) => AutomationConfig) => void;
  editorSeed: number;
  embedMessages: EmbedMessage[];
  previewSubstitute: (text: string) => string;
  onCreateNew: () => void;
}) {
  const source: MessageSource =
    section === "welcome" ? config.welcome_source : config.leave_source;
  const message =
    section === "welcome" ? config.welcome_message : config.leave_message;
  const embedId =
    section === "welcome"
      ? config.welcome_embed_message_id
      : config.leave_embed_message_id;
  const selected = embedMessages.find((m) => m.id === embedId) ?? null;

  const setSource = (next: MessageSource) =>
    updateConfig((c) =>
      section === "welcome"
        ? { ...c, welcome_source: next }
        : { ...c, leave_source: next }
    );
  const setMessage = (markdown: string) =>
    updateConfig((c) =>
      section === "welcome"
        ? { ...c, welcome_message: markdown }
        : { ...c, leave_message: markdown }
    );
  const setEmbedId = (id: string | null) =>
    updateConfig((c) =>
      section === "welcome"
        ? { ...c, welcome_embed_message_id: id }
        : { ...c, leave_embed_message_id: id }
    );

  return (
    <>
      <div>
        <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
          <CFormLabel className="mb-0">{label}</CFormLabel>
          <div className="btn-group btn-group-sm" role="group">
            <Button
              variant={source === "text" ? "primary" : "secondary"}
              size="sm"
              onClick={() => setSource("text")}
            >
              Plain text
            </Button>
            <Button
              variant={source === "embed" ? "primary" : "secondary"}
              size="sm"
              onClick={() => setSource("embed")}
            >
              Embed draft
            </Button>
          </div>
        </div>

        {source === "text" ? (
          <RichMessageEditor
            key={`${section}-${editorSeed}`}
            value={message}
            onChange={setMessage}
            variables={WELCOME_VARIABLES}
            height={180}
            placeholder={placeholder}
          />
        ) : (
          <div className="d-flex flex-column gap-2">
            <CFormSelect
              value={embedId ?? ""}
              onChange={(e) => setEmbedId(e.target.value || null)}
            >
              <option value="">Select an embed draft…</option>
              {embedMessages.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </CFormSelect>
            <div>
              <Button variant="secondary" size="sm" onClick={onCreateNew}>
                Create new embed
              </Button>
            </div>
            {embedId && !selected ? (
              <p className="small text-warning mb-0">
                The selected embed draft no longer exists. Pick another or
                create a new one.
              </p>
            ) : null}
          </div>
        )}
      </div>

      <div>
        <div className="small text-uppercase fw-semibold text-body-secondary mb-2">
          Preview
        </div>
        {source === "text" ? (
          <MessagePreview content={previewSubstitute(message)} mode="text" />
        ) : selected ? (
          <MessagePreview
            content={previewSubstitute(selected.content)}
            embed={selected.embed_json ?? undefined}
            mode="embed"
            showContentWithEmbed
          />
        ) : (
          <p className="small text-body-secondary mb-0">
            Select an embed draft to preview it here.
          </p>
        )}
      </div>
    </>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="d-flex align-items-center justify-content-between gap-3 py-2 border-bottom">
      <div className="min-w-0">
        <div className="fw-medium">{label}</div>
        <p className="mb-0 mt-1 small text-body-secondary">{description}</p>
      </div>
      <Switch checked={checked} onChange={onChange} aria-label={label} />
    </div>
  );
}

function SelectRow({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
}) {
  return (
    <div>
      <CFormLabel>{label}</CFormLabel>
      <CFormSelect
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </CFormSelect>
    </div>
  );
}
