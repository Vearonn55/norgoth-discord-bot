"use client";



import { useEffect, useMemo, useState } from "react";

import { useSearchParams } from "next/navigation";

import { CAlert, CFormCheck, CSpinner } from "@coreui/react";

import {

  cilBan,

  cilCheckCircle,

  cilCommentBubble,

  cilEnvelopeClosed,

  cilFolder,

  cilHistory,

  cilHome,

  cilLink,

  cilMicrophone,

  cilShieldAlt,

  cilTags,

  cilUser,

  cilVoiceOverRecord,

} from "@coreui/icons";

import { Card } from "@/components/ui/card";

import { Button } from "@/components/ui/button";

import { Badge } from "@/components/ui/badge";

import { ConfirmDialog } from "@/components/common/confirm-dialog";

import { PageHeader } from "@/components/layout/page-header";

import { ManagingGuildLabel } from "@/components/layout/managing-guild-label";

import { Icon } from "@/components/ui/icon";

import { MiniFeatureCard } from "@/components/ui/mini-feature-card";

import { MutedSection } from "@/components/ui/feature-muting";

import { useFeatureInfo } from "@/lib/feature-info";

import { formatDict, useLocaleDict } from "@/lib/locale-dict";

import { useFirstGuild } from "@/lib/use-first-guild";

import { colorToHex } from "@/lib/logging";

import {

  mergeLoggingCategories,

  type LoggingCategoryCard,

} from "@/lib/logging-categories";

import { LoggingSetupWizard } from "@/components/security/logging-setup-wizard";

import { LoggingChannelEditModal } from "@/components/security/logging-channel-edit-modal";

import {

  resolveChannelLabel,

  useLoggingConfigStore,

} from "@/stores/logging-config-store";



const CATEGORY_ICONS: Record<string, string[]> = {

  member: cilUser,

  message: cilCommentBubble,

  channel: cilFolder,

  role: cilTags,

  server: cilHome,

  voice: cilMicrophone,

  thread: cilVoiceOverRecord,

  moderation: cilBan,

  security: cilShieldAlt,

  tickets: cilEnvelopeClosed,

  invites: cilLink,

  verification: cilCheckCircle,

};



export function DiscordLogsPage() {

  const searchParams = useSearchParams();

  const dict = useLocaleDict();

  const d = dict.discordLogsPage;

  const info = useFeatureInfo("discordLogs");

  const notConfiguredLabel = dict.common.notConfigured;

  const { guildId, resources, loading: guildLoading, error: guildError } =

    useFirstGuild();



  const config = useLoggingConfigStore((s) => s.config);

  const catalog = useLoggingConfigStore((s) => s.catalog);

  const health = useLoggingConfigStore((s) => s.health);

  const permissions = useLoggingConfigStore((s) => s.permissions);

  const loading = useLoggingConfigStore((s) => s.loading);

  const busy = useLoggingConfigStore((s) => s.busy);

  const error = useLoggingConfigStore((s) => s.error);

  const feedback = useLoggingConfigStore((s) => s.feedback);

  const load = useLoggingConfigStore((s) => s.load);

  const setEnabled = useLoggingConfigStore((s) => s.setEnabled);

  const setChannelEnabled = useLoggingConfigStore((s) => s.setChannelEnabled);

  const reconcile = useLoggingConfigStore((s) => s.reconcile);

  const repair = useLoggingConfigStore((s) => s.repair);

  const reset = useLoggingConfigStore((s) => s.reset);



  const [confirmReset, setConfirmReset] = useState(false);

  const [deleteDiscord, setDeleteDiscord] = useState(false);

  const [editingChannel, setEditingChannel] =

    useState<LoggingCategoryCard | null>(null);

  const [deepLinkConsumed, setDeepLinkConsumed] = useState(false);



  useEffect(() => {

    if (!guildId) return;

    void load(guildId);

  }, [guildId, load]);



  const channels = resources?.channels ?? [];



  const categoryCards = useMemo(

    () => mergeLoggingCategories(catalog, config),

    [catalog, config],

  );



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

    const map = new Map<string, string>();

    for (const item of health?.channels ?? []) map.set(item.key, item.status);

    return map;

  }, [health]);



  // Deep-link from global search: ?channel=member opens that category editor.

  useEffect(() => {

    if (deepLinkConsumed || !config || loading) return;

    const key = searchParams.get("channel");

    if (!key) return;

    const card = categoryCards.find((c) => c.key === key);

    if (!card) return;

    setEditingChannel(card);

    setDeepLinkConsumed(true);

  }, [categoryCards, config, deepLinkConsumed, loading, searchParams]);



  const masterEnabled = Boolean(config?.enabled);



  return (

    <div className="d-flex flex-column gap-4">

      <PageHeader

        title={info?.title ?? dict.featureInfo.discordLogs.title}

        icon={<Icon icon={cilHistory} size="xl" />}

        category="logging"

        description={<ManagingGuildLabel />}

        infoKey="discordLogs"

        masterToggle={

          config

            ? {

                enabled: config.enabled,

                onChange: (checked) =>

                  guildId && void setEnabled(guildId, checked),

                loading: busy,

                label: d.loggingLabel,

                showLabel: false,

              }

            : undefined

        }

      />



      {guildLoading || loading ? (

        <Card>

          <div className="d-flex align-items-center gap-2 text-body-secondary">

            <CSpinner size="sm" />

            {d.loading}

          </div>

        </Card>

      ) : guildError || !guildId ? (

        <Card>

          <CAlert color="warning" className="mb-0">

            {guildError ?? d.botOffline}

          </CAlert>

        </Card>

      ) : !config ? (

        <LoggingSetupWizard

          guildId={guildId}

          channels={channels}

          onComplete={() => {

            void load(guildId);

          }}

        />

      ) : (

        <MutedSection enabled={masterEnabled} className="d-flex flex-column gap-4">

          <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">

            <div className="d-flex align-items-center gap-2">

              <Badge

                variant={config.status === "active" ? "success" : "warning"}

              >

                {config.status === "active" ? d.active : d.draft}

              </Badge>

              <span className="small text-body-secondary">

                {config.norgoth_managed_category && config.category_name

                  ? formatDict(d.categoryNamed, { name: config.category_name })

                  : d.noManagedCategory}

              </span>

            </div>

            <div className="d-flex flex-wrap align-items-center gap-2">

              <Button

                variant="secondary"

                size="sm"

                onClick={() => void reconcile(guildId)}

                disabled={busy}

              >

                {busy ? d.working : d.checkHealth}

              </Button>

              <Button

                variant="secondary"

                size="sm"

                onClick={() => void repair(guildId)}

                disabled={busy}

              >

                {d.repairMissing}

              </Button>

              <Button

                variant="danger"

                size="sm"

                onClick={() => {

                  setDeleteDiscord(false);

                  setConfirmReset(true);

                }}

                disabled={busy}

              >

                {d.reset}

              </Button>

            </div>

          </div>



          {error ? (

            <CAlert color="danger" className="mb-0 py-2">

              {error}

            </CAlert>

          ) : null}

          {permissions?.missing_permissions?.includes("View Audit Log") ? (

            <CAlert color="warning" className="mb-0 py-2">

              {d.missingViewAuditLog}

            </CAlert>

          ) : null}

          {feedback ? (

            <CAlert color="success" className="mb-0 py-2">

              {feedback}

            </CAlert>

          ) : null}



          <div className="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">

            {categoryCards.map((channel) => {

              const eventCount = eventsByChannel.get(channel.key) ?? 0;

              const healthStatus = healthByKey.get(channel.key);

              const eventLabel = formatDict(

                eventCount === 1 ? d.eventCount : d.eventCountPlural,

                { count: eventCount },

              );

              const description = !channel.configured

                ? notConfiguredLabel

                : [

                    eventLabel,

                    channel.channel_id

                      ? resolveChannelLabel(channel, channels)

                      : d.noChannel,

                    healthStatus && healthStatus !== "ok" ? healthStatus : null,

                  ]

                    .filter(Boolean)

                    .join(" · ");



              return (

                <div key={channel.key} className="col">

                  <MiniFeatureCard

                    icon={CATEGORY_ICONS[channel.key] ?? cilFolder}

                    name={channel.label}

                    description={description}

                    category="logging"

                    enabled={channel.configured ? channel.enabled : false}

                    enabledAccent={

                      channel.configured

                        ? colorToHex(channel.default_color)

                        : undefined

                    }

                    statusLabel={

                      channel.configured ? undefined : notConfiguredLabel

                    }

                    toggleDisabled={

                      busy || !masterEnabled || !channel.configured

                    }

                    onToggle={(checked) =>

                      void setChannelEnabled(guildId, channel.key, checked)

                    }

                    onClick={() => setEditingChannel(channel)}

                  />

                </div>

              );

            })}

          </div>



          <ConfirmDialog

            visible={confirmReset}

            title={d.resetTitle}

            message={

              <div className="d-flex flex-column gap-3">

                <p className="mb-0 text-body-secondary">{d.resetMessage}</p>

                <CFormCheck

                  id="delete-discord-logging"

                  label={d.resetDeleteDiscord}

                  checked={deleteDiscord}

                  onChange={(e) => setDeleteDiscord(e.target.checked)}

                />

              </div>

            }

            confirmLabel={d.reset}

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

                void load(guildId);

                void reconcile(guildId);

              }}

            />

          ) : null}

        </MutedSection>

      )}

    </div>

  );

}


