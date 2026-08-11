"use client";

import { useEffect, useMemo, useState } from "react";
import { CAlert, CFormCheck, CSpinner } from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { useFirstGuild } from "@/lib/use-first-guild";
import { LoggingSetupWizard } from "@/components/security/logging-setup-wizard";
import { LoggingChannelEditModal } from "@/components/security/logging-channel-edit-modal";
import {
  colorToHex,
  resolveChannelLabel,
  useLoggingConfigStore,
  type LoggingChannelConfig,
  type LoggingChannelHealth,
} from "@/stores/logging-config-store";

function healthVariant(
  status: LoggingChannelHealth["status"]
): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "ok":
      return "success";
    case "missing":
      return "danger";
    case "error":
      return "warning";
    default:
      return "neutral";
  }
}

export function LoggingConfigurationsPanel() {
  const { guildId, resources, loading: guildLoading, error: guildError } =
    useFirstGuild();

  const config = useLoggingConfigStore((s) => s.config);
  const catalog = useLoggingConfigStore((s) => s.catalog);
  const health = useLoggingConfigStore((s) => s.health);
  const loading = useLoggingConfigStore((s) => s.loading);
  const busy = useLoggingConfigStore((s) => s.busy);
  const error = useLoggingConfigStore((s) => s.error);
  const feedback = useLoggingConfigStore((s) => s.feedback);
  const load = useLoggingConfigStore((s) => s.load);
  const setEnabled = useLoggingConfigStore((s) => s.setEnabled);
  const reconcile = useLoggingConfigStore((s) => s.reconcile);
  const repair = useLoggingConfigStore((s) => s.repair);
  const reset = useLoggingConfigStore((s) => s.reset);

  const [confirmReset, setConfirmReset] = useState(false);
  const [deleteDiscord, setDeleteDiscord] = useState(false);
  const [editingChannel, setEditingChannel] =
    useState<LoggingChannelConfig | null>(null);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  const channels = resources?.channels ?? [];
  const channelDisplayName = (channel: LoggingChannelConfig): string =>
    resolveChannelLabel(channel, channels);

  const eventsByChannel = useMemo(() => {
    const map = new Map<string, number>();
    if (config) {
      for (const event of config.events) {
        if (!event.enabled || !event.channel_key) continue;
        map.set(event.channel_key, (map.get(event.channel_key) ?? 0) + 1);
      }
    }
    return map;
  }, [config]);

  const healthByKey = useMemo(() => {
    const map = new Map<string, LoggingChannelHealth>();
    for (const item of health?.channels ?? []) map.set(item.key, item);
    return map;
  }, [health]);

  if (guildLoading || loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading logging configuration…
        </div>
      </Card>
    );
  }

  if (guildError || !guildId) {
    return (
      <Card>
        <CAlert color="warning" className="mb-0">
          {guildError ?? "Bot is offline or not in any server yet."}
        </CAlert>
      </Card>
    );
  }

  // STATE A — no configuration yet: run the first-time setup wizard.
  if (!config) {
    return (
      <div className="d-flex flex-column gap-3">
        <LoggingSetupWizard
          guildId={guildId}
          channels={channels}
          onComplete={() => {
            void load(guildId);
          }}
        />
      </div>
    );
  }

  // STATE B — configured.
  return (
    <div className="d-flex flex-column gap-4">
      <Card>
        <div className="d-flex flex-column gap-3">
          <div className="d-flex flex-wrap align-items-start justify-content-between gap-3">
            <div>
              <div className="d-flex align-items-center gap-2">
                <h2 className="h5 mb-0 fw-semibold">Logging Configuration</h2>
                <Badge variant={config.status === "active" ? "success" : "warning"}>
                  {config.status === "active" ? "Active" : "Draft"}
                </Badge>
              </div>
              <p className="mt-1 mb-0 small text-body-secondary">
                {config.norgoth_managed_category && config.category_name
                  ? `Category: ${config.category_name}`
                  : "No managed category."}
              </p>
            </div>
            <div className="d-flex align-items-center gap-2">
              <span className="small fw-semibold">Logging enabled</span>
              <Switch
                checked={config.enabled}
                disabled={busy}
                onChange={(checked) => void setEnabled(guildId, checked)}
                aria-label="Master logging enabled"
              />
            </div>
          </div>

          {error ? (
            <CAlert color="danger" className="mb-0 py-2">
              {error}
            </CAlert>
          ) : null}
          {feedback ? (
            <CAlert color="success" className="mb-0 py-2">
              {feedback}
            </CAlert>
          ) : null}

          <div className="d-flex flex-column gap-2">
            {config.channels.map((channel) => {
              const item = healthByKey.get(channel.key);
              return (
                <div
                  key={channel.id ?? channel.key}
                  className="d-flex flex-wrap align-items-center justify-content-between gap-2 border rounded p-3"
                >
                  <div className="d-flex align-items-center gap-2">
                    <span
                      className="rounded-circle border"
                      style={{
                        width: 14,
                        height: 14,
                        backgroundColor: colorToHex(channel.default_color),
                      }}
                    />
                    <span className="fw-medium">
                      {channelDisplayName(channel)}
                    </span>
                    {channel.norgoth_managed ? (
                      <Badge variant="info">Managed</Badge>
                    ) : (
                      <Badge variant="neutral">Existing</Badge>
                    )}
                  </div>
                  <div className="d-flex align-items-center gap-2 small text-body-secondary">
                    <span>
                      {eventsByChannel.get(channel.key) ?? 0} event
                      {(eventsByChannel.get(channel.key) ?? 0) === 1 ? "" : "s"}
                    </span>
                    {item ? (
                      <Badge variant={healthVariant(item.status)}>
                        {item.status}
                      </Badge>
                    ) : null}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setEditingChannel(channel)}
                      disabled={busy}
                    >
                      Edit
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="d-flex flex-wrap align-items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => void reconcile(guildId)}
              disabled={busy}
            >
              {busy ? "Working…" : "Check health"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => void repair(guildId)}
              disabled={busy}
            >
              Repair missing
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setDeleteDiscord(false);
                setConfirmReset(true);
              }}
              disabled={busy}
            >
              Reset
            </Button>
          </div>
        </div>
      </Card>

      <ConfirmDialog
        visible={confirmReset}
        title="Reset logging configuration?"
        message={
          <div className="d-flex flex-column gap-3">
            <p className="mb-0 text-body-secondary">
              This removes the saved logging configuration and routing. By
              default, Discord channels are left in place.
            </p>
            <CFormCheck
              id="delete-discord-logging"
              label="Also delete Norgoth-managed log channels and category in Discord"
              checked={deleteDiscord}
              onChange={(e) => setDeleteDiscord(e.target.checked)}
            />
          </div>
        }
        confirmLabel="Reset"
        destructive
        busy={busy}
        onConfirm={() => {
          void reset(guildId, deleteDiscord).then((ok) => {
            if (ok) {
              setConfirmReset(false);
              setDeleteDiscord(false);
            }
          });
        }}
        onCancel={() => {
          setConfirmReset(false);
          setDeleteDiscord(false);
        }}
      />

      {editingChannel ? (
        <LoggingChannelEditModal
          visible={Boolean(editingChannel)}
          guildId={guildId}
          channel={editingChannel}
          catalog={catalog}
          events={config.events}
          onClose={() => setEditingChannel(null)}
          onSaved={() => {
            setEditingChannel(null);
            void reconcile(guildId);
          }}
        />
      ) : null}
    </div>
  );
}
