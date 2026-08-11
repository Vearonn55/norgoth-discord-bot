"use client";

import { useEffect, useState } from "react";
import {
  CBadge,
  CFormInput,
  CFormSelect,
  CSpinner,
} from "@coreui/react";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useGuildStore } from "@/stores/guild-store";
import {
  useContentNotificationsStore,
  type ContentPlatform,
  type ResolvedCreator,
} from "@/stores/content-notifications-store";
import { Button } from "@/components/ui/button";
import { ChannelSelect } from "@/components/ui/channel-select";
import { RoleSelect } from "@/components/ui/role-select";
import { MessagePreview } from "@/components/discord/message-preview";
import { apiUrl } from "@/lib/api";

const PLATFORMS: Array<{ id: ContentPlatform; label: string }> = [
  { id: "youtube", label: "YouTube" },
  { id: "twitch", label: "Twitch" },
  { id: "kick", label: "Kick" },
  { id: "x", label: "X" },
  { id: "tiktok", label: "TikTok" },
];

export function AccountsPanel() {
  const { guildId } = useFirstGuild();
  const resources = useGuildStore((s) => s.resources);
  const accounts = useContentNotificationsStore((s) => s.accounts);
  const platforms = useContentNotificationsStore((s) => s.platforms);
  const templates = useContentNotificationsStore((s) => s.templates);
  const styles = useContentNotificationsStore((s) => s.styles);
  const workerOnline = useContentNotificationsStore((s) => s.workerOnline);
  const loading = useContentNotificationsStore((s) => s.loading);
  const saving = useContentNotificationsStore((s) => s.saving);
  const error = useContentNotificationsStore((s) => s.error);
  const loadAccounts = useContentNotificationsStore((s) => s.loadAccounts);
  const loadTemplates = useContentNotificationsStore((s) => s.loadTemplates);
  const loadStyles = useContentNotificationsStore((s) => s.loadStyles);
  const resolveAccount = useContentNotificationsStore((s) => s.resolveAccount);
  const createAccount = useContentNotificationsStore((s) => s.createAccount);
  const deleteAccount = useContentNotificationsStore((s) => s.deleteAccount);
  const toggleAccount = useContentNotificationsStore((s) => s.toggleAccount);
  const testNotification = useContentNotificationsStore(
    (s) => s.testNotification
  );

  const [wizardOpen, setWizardOpen] = useState(false);
  const [platform, setPlatform] = useState<ContentPlatform>("youtube");
  const [url, setUrl] = useState("");
  const [resolved, setResolved] = useState<ResolvedCreator | null>(null);
  const [channelId, setChannelId] = useState("");
  const [roleId, setRoleId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [styleId, setStyleId] = useState("");
  const [previewPayload, setPreviewPayload] = useState<{
    content?: string;
  } | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void loadAccounts(guildId);
    void loadTemplates(guildId);
    void loadStyles(guildId);
  }, [guildId, loadAccounts, loadTemplates, loadStyles]);

  async function handleResolve() {
    if (!guildId || !url.trim()) return;
    setFeedback(null);
    try {
      const creator = await resolveAccount(guildId, platform, url.trim());
      setResolved(creator);
      const template = templates.find(
        (t) => t.platform_default_for === platform
      );
      if (template) setTemplateId(template.id);
      const response = await fetch(
        apiUrl(`/guilds/${guildId}/content-notifications/preview`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            platform,
            content: template?.content || "",
            ping_role_id: roleId || null,
          }),
        }
      );
      if (response.ok) {
        const data = await response.json();
        setPreviewPayload(data.payload);
      }
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Resolve failed");
      setResolved(null);
    }
  }

  async function handleSave() {
    if (!guildId || !resolved || !channelId) return;
    setFeedback(null);
    try {
      await createAccount(guildId, {
        platform,
        url: url.trim(),
        destination_channel_id: channelId,
        ping_role_id: roleId || null,
        template_id: templateId || null,
        sender_style_id: styleId || null,
      });
      setWizardOpen(false);
      setUrl("");
      setResolved(null);
      setFeedback("Account saved.");
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Save failed");
    }
  }

  const platformMeta = (id: string) =>
    platforms.find((p) => p.platform === id);

  return (
    <div className="d-flex flex-column gap-4">
      <div className="d-flex align-items-center justify-content-between gap-3 flex-wrap">
        <div>
          <p className="mb-0 small text-body-secondary">
            Monitor creators and deliver alerts through managed Discord webhooks.
            Admins never paste platform API keys or webhook URLs.
          </p>
          <div className="mt-2 d-flex gap-2 flex-wrap">
            {PLATFORMS.map((p) => {
              const meta = platformMeta(p.id);
              const blocked = meta && !meta.available;
              return (
                <CBadge
                  key={p.id}
                  color={blocked ? "secondary" : "success"}
                  className="text-uppercase"
                >
                  {p.label}
                  {blocked ? " · blocked" : ""}
                </CBadge>
              );
            })}
            <CBadge color={workerOnline ? "success" : "warning"}>
              Worker {workerOnline ? "online" : "offline"}
            </CBadge>
          </div>
        </div>
        <Button type="button" onClick={() => setWizardOpen((v) => !v)}>
          {wizardOpen ? "Close" : "Add Account"}
        </Button>
      </div>

      {feedback ? <p className="small text-body-secondary mb-0">{feedback}</p> : null}
      {error ? <p className="small text-danger mb-0">{error}</p> : null}

      {wizardOpen ? (
        <div className="border rounded p-4 d-flex flex-column gap-3">
          <h3 className="h6 mb-0">Add monitored account</h3>
          <div className="row g-3">
            <div className="col-md-4">
              <label className="form-label small">Platform</label>
              <CFormSelect
                value={platform}
                onChange={(e) => {
                  setPlatform(e.target.value as ContentPlatform);
                  setResolved(null);
                }}
              >
                {PLATFORMS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                    {platformMeta(p.id)?.available === false ? " (unavailable)" : ""}
                  </option>
                ))}
              </CFormSelect>
            </div>
            <div className="col-md-8">
              <label className="form-label small">Creator / channel URL</label>
              <div className="d-flex gap-2">
                <CFormInput
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://..."
                />
                <Button type="button" variant="secondary" onClick={() => void handleResolve()}>
                  Resolve
                </Button>
              </div>
            </div>
          </div>

          {resolved ? (
            <div className="d-flex align-items-center gap-3 border rounded p-3">
              {resolved.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={resolved.avatar_url}
                  alt=""
                  width={48}
                  height={48}
                  className="rounded-circle"
                />
              ) : null}
              <div>
                <div className="fw-semibold">{resolved.display_name}</div>
                <div className="small text-body-secondary text-uppercase">
                  {resolved.platform} · {resolved.username}
                </div>
                {resolved.reason ? (
                  <div className="small text-warning mt-1">{resolved.reason}</div>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="row g-3">
            <div className="col-md-4">
              <label className="form-label small">Discord channel</label>
              <ChannelSelect
                channels={resources?.channels ?? []}
                value={channelId}
                onChange={setChannelId}
              />
            </div>
            <div className="col-md-4">
              <label className="form-label small">Ping role (optional)</label>
              <RoleSelect
                roles={resources?.roles ?? []}
                value={roleId}
                onChange={setRoleId}
              />
            </div>
            <div className="col-md-4">
              <label className="form-label small">Template</label>
              <CFormSelect
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">Default</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </CFormSelect>
            </div>
            <div className="col-md-4">
              <label className="form-label small">Sender style</label>
              <CFormSelect
                value={styleId}
                onChange={(e) => setStyleId(e.target.value)}
              >
                <option value="">Default Norgoth</option>
                {styles.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.display_name}
                  </option>
                ))}
              </CFormSelect>
            </div>
          </div>

          {previewPayload ? (
            <div>
              <div className="small text-body-secondary mb-2">Preview</div>
              <MessagePreview content={previewPayload.content || ""} />
            </div>
          ) : null}

          <div>
            <Button
              type="button"
              disabled={saving || !resolved || !channelId}
              onClick={() => void handleSave()}
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      ) : null}

      {loading ? (
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" /> Loading accounts…
        </div>
      ) : null}

      <div className="d-flex flex-column gap-2">
        {accounts.map((account) => (
          <div
            key={account.id}
            className="border rounded p-3 d-flex align-items-center gap-3 flex-wrap"
          >
            {account.source?.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={account.source.avatar_url}
                alt=""
                width={40}
                height={40}
                className="rounded-circle"
              />
            ) : (
              <div
                className="rounded-circle bg-secondary"
                style={{ width: 40, height: 40 }}
              />
            )}
            <div className="flex-grow-1 min-w-0">
              <div className="fw-semibold text-truncate">
                {account.source?.display_name || "Unknown"}
              </div>
              <div className="small text-body-secondary text-uppercase">
                {account.source?.platform} · {account.status.replaceAll("_", " ")}
              </div>
            </div>
            <CBadge color={account.enabled ? "success" : "secondary"}>
              {account.enabled ? "Enabled" : "Paused"}
            </CBadge>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() =>
                void toggleAccount(guildId!, account.id, !account.enabled)
              }
            >
              {account.enabled ? "Pause" : "Enable"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                void testNotification(guildId!, account.id)
                  .then(() => setFeedback("Test notification queued."))
                  .catch((err: unknown) =>
                    setFeedback(
                      err instanceof Error ? err.message : "Test failed"
                    )
                  );
              }}
            >
              Test
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={() => void deleteAccount(guildId!, account.id)}
            >
              Delete
            </Button>
          </div>
        ))}
        {!loading && accounts.length === 0 ? (
          <p className="text-body-secondary mb-0">
            No monitored accounts yet. Add a creator URL to get started.
          </p>
        ) : null}
      </div>
    </div>
  );
}
