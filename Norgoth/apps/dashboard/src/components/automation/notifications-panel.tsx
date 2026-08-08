"use client";

import { useEffect } from "react";
import {
  CAlert,
  CCol,
  CFormInput,
  CFormLabel,
  CFormSelect,
  CRow,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useNotificationsStore,
  type NotificationPlatform,
} from "@/stores/automation-store";

export function NotificationsPanel() {
  const { guildId, resources, loading, error, reload } = useFirstGuild();

  const creators = useNotificationsStore((s) => s.creators);
  const twitchConfigured = useNotificationsStore((s) => s.twitchConfigured);
  const draft = useNotificationsStore((s) => s.draft);
  const busy = useNotificationsStore((s) => s.busy);
  const feedback = useNotificationsStore((s) => s.feedback);
  const feedbackIsError = useNotificationsStore((s) => s.feedbackIsError);
  const setDraft = useNotificationsStore((s) => s.setDraft);
  const load = useNotificationsStore((s) => s.load);
  const persist = useNotificationsStore((s) => s.persist);
  const addCreator = useNotificationsStore((s) => s.addCreator);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading notifications…
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="small text-body-secondary">{error}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  const channels = resources?.channels ?? [];
  const roles = (resources?.roles ?? []).filter((role) => !role.managed);
  const channelNames = new Map(
    channels.map((channel) => [channel.id, channel.name])
  );

  return (
    <div className="d-flex flex-column gap-4">
      {!twitchConfigured ? (
        <CAlert color="warning" className="mb-0">
          <strong>Twitch not configured.</strong> Add{" "}
          <code>TWITCH_CLIENT_ID</code> and <code>TWITCH_CLIENT_SECRET</code> to{" "}
          <code>Norgoth/.env</code> to enable Twitch live notifications. YouTube
          works without keys.
        </CAlert>
      ) : null}

      <Card>
        <div className="d-flex flex-column gap-3">
          <div>
            <h2 className="h5 mb-0 fw-semibold">Add a Creator</h2>
            <p className="mt-1 small text-body-secondary">
              The bot checks every ~2 minutes for new YouTube uploads and
              Twitch streams going live. Message variables: {"{creator}"},{" "}
              {"{title}"}, {"{url}"}.
            </p>
          </div>

          <CRow className="g-3">
            <CCol md={4}>
              <CFormLabel>Platform</CFormLabel>
              <CFormSelect
                value={draft.platform}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    platform: event.target.value as NotificationPlatform,
                  }))
                }
              >
                <option value="youtube">YouTube</option>
                <option value="twitch" disabled={!twitchConfigured}>
                  Twitch{twitchConfigured ? "" : " (not configured)"}
                </option>
              </CFormSelect>
            </CCol>

            <CCol md={8}>
              <CFormLabel>
                {draft.platform === "youtube"
                  ? "YouTube channel ID / URL"
                  : "Twitch username / URL"}
              </CFormLabel>
              <CFormInput
                value={draft.handle}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    handle: event.target.value,
                  }))
                }
                maxLength={100}
                placeholder={
                  draft.platform === "youtube"
                    ? "UCxxxxxxxxxxxxxxxxxxxxxx"
                    : "somestreamer"
                }
              />
            </CCol>

            <CCol md={4}>
              <CFormLabel>Display name</CFormLabel>
              <CFormInput
                value={draft.display_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    display_name: event.target.value,
                  }))
                }
                maxLength={100}
              />
            </CCol>

            <CCol md={4}>
              <CFormLabel>Announcement channel</CFormLabel>
              <CFormSelect
                value={draft.channel_id ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    channel_id: event.target.value || null,
                  }))
                }
              >
                <option value="">Select a channel…</option>
                {channels.map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    #{channel.name}
                  </option>
                ))}
              </CFormSelect>
            </CCol>

            <CCol md={4}>
              <CFormLabel>Ping role</CFormLabel>
              <CFormSelect
                value={draft.role_id ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    role_id: event.target.value || null,
                  }))
                }
              >
                <option value="">No ping</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    @{role.name}
                  </option>
                ))}
              </CFormSelect>
            </CCol>

            <CCol xs={12}>
              <CFormLabel>Custom message (optional)</CFormLabel>
              <CFormInput
                value={draft.message}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    message: event.target.value,
                  }))
                }
                maxLength={500}
                placeholder="🔴 {creator} is live: {title} — {url}"
              />
            </CCol>
          </CRow>

          <div className="d-flex align-items-center gap-3">
            <Button
              variant="primary"
              onClick={() => void addCreator(guildId)}
              disabled={busy || creators.length >= 25}
            >
              {busy ? "Saving…" : "Add Creator"}
            </Button>

            {feedback ? (
              <span
                className={`text-xs ${
                  feedbackIsError ? "text-danger" : "text-success"
                }`}
              >
                {feedback}
              </span>
            ) : null}
          </div>
        </div>
      </Card>

      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex align-items-center justify-content-between gap-3">
            <div>
              <h2 className="h5 mb-0 fw-semibold">Watched Creators</h2>
              <p className="mt-1 small text-body-secondary">
                {creators.length} / 25 creators.
              </p>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => void load(guildId)}
            >
              Refresh
            </Button>
          </div>

          {creators.length === 0 ? (
            <p className="border rounded p-5 small text-body-secondary">
              No creators configured yet.
            </p>
          ) : (
            <div className="d-flex flex-column gap-2">
              {creators.map((creator) => (
                <div
                  key={creator.id}
                  className="d-flex flex-column flex-md-row align-items-md-center justify-content-md-between gap-2 border rounded px-3 py-2"
                >
                  <div className="d-flex flex-wrap align-items-center gap-3">
                    <Switch
                      checked={creator.enabled}
                      onChange={(checked) =>
                        void persist(
                          guildId,
                          creators.map((item) =>
                            item.id === creator.id
                              ? { ...item, enabled: checked }
                              : item
                          )
                        )
                      }
                      aria-label={`Enable ${creator.handle}`}
                    />
                    <Badge
                      variant={
                        creator.platform === "twitch" ? "info" : "danger"
                      }
                    >
                      {creator.platform}
                    </Badge>
                    <span className="small">
                      {creator.display_name || creator.handle}
                    </span>
                    {creator.channel_id ? (
                      <span className="small text-body-secondary">
                        → #
                        {channelNames.get(creator.channel_id) ??
                          creator.channel_id}
                      </span>
                    ) : null}
                  </div>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      void persist(
                        guildId,
                        creators.filter((item) => item.id !== creator.id)
                      )
                    }
                    disabled={busy}
                  >
                    Delete
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
