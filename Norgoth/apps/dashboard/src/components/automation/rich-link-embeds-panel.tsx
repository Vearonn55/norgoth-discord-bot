"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CAlert,
  CFormCheck,
  CFormInput,
  CFormLabel,
  CSpinner,
} from "@coreui/react";
import { SectionCard } from "@/components/ui/section-card";
import { ChannelSelect } from "@/components/ui/channel-select";
import { ChannelPickerToolbar } from "@/components/ui/refresh-channels-button";
import { Button } from "@/components/ui/button";
import { NumberInput } from "@/components/ui/number-input";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { MutedSection } from "@/components/ui/feature-muting";
import { PageHeader } from "@/components/layout/page-header";
import { PageActionFooter } from "@/components/layout/page-action-footer";
import { useFirstGuild } from "@/stores/guild-store";
import {
  FIXED_REWRITE_HOSTS,
  useRichLinkEmbedsStore,
  type RichLinkEmbedsConfig,
  type RichLinkPlatforms,
} from "@/stores/rich-link-embeds-store";
import { Icon } from "@/components/ui/icon";
import {
  cilBell,
  cilImage,
  cilLink,
  cilMediaPlay,
  cilShare,
  cilUser,
} from "@coreui/icons";
import { useFeatureInfo } from "@/lib/feature-info";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

const PLATFORM_ICONS: Record<keyof RichLinkPlatforms, string | string[]> = {
  twitter: cilShare,
  bluesky: cilBell,
  tiktok: cilImage,
  instagram: cilUser,
  reddit: cilLink,
  pixiv: cilImage,
  youtube_shorts: cilMediaPlay,
};

const PLATFORM_NAMES: Record<keyof RichLinkPlatforms, string> = {
  twitter: "Twitter / X",
  bluesky: "Bluesky",
  tiktok: "TikTok",
  instagram: "Instagram",
  reddit: "Reddit",
  pixiv: "Pixiv",
  youtube_shorts: "YouTube Shorts",
};

function normalizeHost(host: string): string {
  let h = host.toLowerCase();
  if (h.startsWith("www.")) h = h.slice(4);
  return h;
}

function previewRewrite(
  url: string,
  config: RichLinkEmbedsConfig,
): string | null {
  try {
    const parsed = new URL(url.trim());
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    const host = normalizeHost(parsed.hostname);
    const path = parsed.pathname || "";
    const lower = path.toLowerCase();

    type Rule = {
      key: keyof RichLinkPlatforms;
      hosts: string[];
      match: () => boolean;
      rewrite: () => string;
    };

    const rules: Rule[] = [
      {
        key: "twitter",
        hosts: ["twitter.com", "x.com", "mobile.twitter.com", "mobile.x.com"],
        match: () => lower.includes("/status/"),
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.twitter}${path}`,
      },
      {
        key: "bluesky",
        hosts: ["bsky.app"],
        match: () => lower.includes("/profile/") && lower.includes("/post/"),
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.bluesky}${path}`,
      },
      {
        key: "tiktok",
        hosts: ["tiktok.com", "vm.tiktok.com"],
        match: () => lower.includes("/video/") || lower.includes("/t/"),
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.tiktok}${path}`,
      },
      {
        key: "instagram",
        hosts: ["instagram.com"],
        match: () =>
          ["/p/", "/reel/", "/reels/", "/stories/"].some((t) =>
            lower.includes(t),
          ),
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.instagram}${path}`,
      },
      {
        key: "reddit",
        hosts: ["reddit.com", "old.reddit.com", "redd.it"],
        match: () => {
          if (lower.includes("/s/")) return false;
          return (
            lower.includes("/comments/") ||
            /^\/[a-z0-9]+\/?$/i.test(path) ||
            lower.includes("/r/") ||
            lower.includes("/user/") ||
            lower.includes("/u/")
          );
        },
        rewrite: () => `https://${FIXED_REWRITE_HOSTS.reddit}${path}`,
      },
      {
        key: "pixiv",
        hosts: ["pixiv.net"],
        match: () =>
          lower.includes("/artworks/") ||
          lower.includes("/artwork/") ||
          (lower.includes("member_illust.php") &&
            parsed.searchParams.has("illust_id")),
        rewrite: () => {
          if (lower.includes("member_illust.php")) {
            const id = parsed.searchParams.get("illust_id");
            return id
              ? `https://${FIXED_REWRITE_HOSTS.pixiv}/artworks/${id}`
              : "";
          }
          return `https://${FIXED_REWRITE_HOSTS.pixiv}${path}`;
        },
      },
      {
        key: "youtube_shorts",
        hosts: ["youtube.com", "m.youtube.com"],
        match: () => /^\/shorts\/[A-Za-z0-9_-]{6,}/.test(path),
        rewrite: () => {
          const m = path.match(/^\/shorts\/([A-Za-z0-9_-]{6,})/);
          return m
            ? `https://${FIXED_REWRITE_HOSTS.youtube_shorts}/${m[1]}`
            : "";
        },
      },
    ];

    for (const rule of rules) {
      if (!config.platforms[rule.key]) continue;
      if (!rule.hosts.includes(host)) continue;
      if (!rule.match()) continue;
      const out = rule.rewrite();
      return out || null;
    }
    return null;
  } catch {
    return null;
  }
}

export function RichLinkEmbedsPanel() {
  const dict = useLocaleDict();
  const d = dict.richLinkEmbedsPage;
  const { guildId, resources, loading: guildLoading } = useFirstGuild();
  const config = useRichLinkEmbedsStore((s) => s.config);
  const loading = useRichLinkEmbedsStore((s) => s.loading);
  const saving = useRichLinkEmbedsStore((s) => s.saving);
  const error = useRichLinkEmbedsStore((s) => s.error);
  const load = useRichLinkEmbedsStore((s) => s.load);
  const save = useRichLinkEmbedsStore((s) => s.save);
  const info = useFeatureInfo("richLinkEmbeds");
  const [draft, setDraft] = useState<RichLinkEmbedsConfig | null>(null);
  const [testUrl, setTestUrl] = useState("");

  const platformMeta = useMemo(
    () =>
      (
        Object.keys(PLATFORM_NAMES) as Array<keyof RichLinkPlatforms>
      ).map((key) => {
        const descKey = {
          twitter: d.platformDescTwitter,
          bluesky: d.platformDescBluesky,
          tiktok: d.platformDescTiktok,
          instagram: d.platformDescInstagram,
          reddit: d.platformDescReddit,
          pixiv: d.platformDescPixiv,
          youtube_shorts: d.platformDescYoutubeShorts,
        }[key];
        return {
          key,
          name: PLATFORM_NAMES[key],
          description: formatDict(descKey, { host: FIXED_REWRITE_HOSTS[key] }),
          icon: PLATFORM_ICONS[key],
        };
      }),
    [d],
  );

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  useEffect(() => {
    if (config) setDraft(config);
  }, [config]);

  const preview = useMemo(
    () => (draft && testUrl.trim() ? previewRewrite(testUrl, draft) : null),
    [draft, testUrl],
  );

  if (guildLoading || loading || !draft) {
    return (
      <div className="d-flex align-items-center gap-2">
        <CSpinner size="sm" /> {d.loading}
      </div>
    );
  }

  if (!guildId) {
    return <p className="text-body-secondary">{d.selectServer}</p>;
  }

  function patch(partial: Partial<RichLinkEmbedsConfig>) {
    setDraft((prev) => (prev ? { ...prev, ...partial } : prev));
  }

  function patchPlatform(key: keyof RichLinkPlatforms, enabled: boolean) {
    setDraft((prev) =>
      prev
        ? { ...prev, platforms: { ...prev.platforms, [key]: enabled } }
        : prev,
    );
  }

  async function setEnabledAndSave(checked: boolean) {
    if (!draft || !guildId) return;
    const next = {
      ...draft,
      enabled: checked,
      rewrite_hosts: { ...FIXED_REWRITE_HOSTS },
    };
    setDraft(next);
    await save(guildId, next);
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(config);
  const disclosureHosts = Object.values(FIXED_REWRITE_HOSTS).join(", ");
  const featureTitle = info?.title ?? "Link Embeds";

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={featureTitle}
        category="messages"
        icon={<Icon icon={cilLink} size="xl" />}
        description={info?.description}
        infoKey="richLinkEmbeds"
        masterToggle={{
          enabled: draft.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
          label: featureTitle,
          showLabel: false,
        }}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      {!draft.enabled ? (
        <CAlert color="secondary" className="mb-0">
          {d.pausedAlert}
        </CAlert>
      ) : null}

      <MutedSection enabled={draft.enabled} className="d-flex flex-column gap-4">
        <SectionCard
          level="primary"
          category="messages"
          header={d.platforms}
        >
          <div className="d-flex flex-wrap gap-3 p-1">
            {platformMeta.map((platform) => (
              <div
                key={platform.key}
                style={{ minWidth: 260, flex: "1 1 260px" }}
              >
                <MiniFeatureCard
                  icon={platform.icon}
                  name={platform.name}
                  description={platform.description}
                  category="messages"
                  enabled={draft.platforms[platform.key]}
                  disabledAccent={
                    draft.enabled ? "var(--cui-danger)" : undefined
                  }
                  onToggle={(checked) => patchPlatform(platform.key, checked)}
                  onClick={() =>
                    patchPlatform(
                      platform.key,
                      !draft.platforms[platform.key],
                    )
                  }
                />
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard level="secondary" category="messages" header={d.channels}>
          <div className="d-flex flex-column gap-3 p-1">
            <div>
              <ChannelPickerToolbar label={d.allowlist} />
              <ChannelSelect
                channels={resources?.channels ?? []}
                value=""
                onChange={(id) => {
                  if (!id || draft.channel_allowlist.includes(id)) return;
                  patch({
                    channel_allowlist: [...draft.channel_allowlist, id],
                  });
                }}
              />
              <ChannelChips
                ids={draft.channel_allowlist}
                channels={resources?.channels ?? []}
                unavailableLabel={dict.common.channelUnavailable}
                onRemove={(id) =>
                  patch({
                    channel_allowlist: draft.channel_allowlist.filter(
                      (x) => x !== id,
                    ),
                  })
                }
              />
            </div>
            <div>
              <CFormLabel>{d.denylist}</CFormLabel>
              <ChannelSelect
                channels={resources?.channels ?? []}
                value=""
                onChange={(id) => {
                  if (!id || draft.channel_denylist.includes(id)) return;
                  patch({
                    channel_denylist: [...draft.channel_denylist, id],
                  });
                }}
              />
              <ChannelChips
                ids={draft.channel_denylist}
                channels={resources?.channels ?? []}
                unavailableLabel={dict.common.channelUnavailable}
                onRemove={(id) =>
                  patch({
                    channel_denylist: draft.channel_denylist.filter(
                      (x) => x !== id,
                    ),
                  })
                }
              />
            </div>
          </div>
        </SectionCard>

        <SectionCard level="secondary" category="messages" header={d.behavior}>
          <div className="d-flex flex-column gap-3 p-1">
            <CFormCheck
              id="rle-ignore-bots"
              label={d.ignoreBots}
              checked={draft.ignore_bots}
              onChange={(e) => patch({ ignore_bots: e.target.checked })}
            />
            <CFormCheck
              id="rle-process-edits"
              label={d.processEdits}
              checked={draft.process_edits}
              onChange={(e) => patch({ process_edits: e.target.checked })}
            />
            <div style={{ maxWidth: 240 }}>
              <CFormLabel>{d.maxLinks}</CFormLabel>
              <NumberInput
                value={draft.max_links_per_message}
                defaultValue={3}
                min={1}
                max={10}
                onCommit={(next) => patch({ max_links_per_message: next })}
              />
            </div>
            <p className="small text-body-secondary mb-0">{d.suppressNote}</p>
          </div>
        </SectionCard>

        <SectionCard
          level="secondary"
          category="messages"
          header={d.disclosureHeader}
        >
          <div className="d-flex flex-column gap-3 p-1">
            <CAlert color="info" className="mb-0">
              {formatDict(d.disclosureBody, { hosts: disclosureHosts })}
            </CAlert>
            <CFormCheck
              id="rle-disclosure"
              label={d.disclosureAck}
              checked={draft.disclosure_acknowledged}
              onChange={(e) =>
                patch({ disclosure_acknowledged: e.target.checked })
              }
            />
          </div>
        </SectionCard>

        <SectionCard level="secondary" category="messages" header={d.testUrl}>
          <div className="d-flex flex-column gap-2 p-1">
            <CFormLabel>{d.testUrlHelp}</CFormLabel>
            <CFormInput
              value={testUrl}
              onChange={(e) => setTestUrl(e.target.value)}
              placeholder="https://x.com/user/status/123"
            />
            {testUrl.trim() ? (
              <p className="small mb-0 text-body-secondary">
                {preview
                  ? `${d.preview}: ${preview}`
                  : d.noMatch}
              </p>
            ) : null}
          </div>
        </SectionCard>
      </MutedSection>

      <PageActionFooter>
        <Button
          variant="primary"
          disabled={saving || !draft.enabled || !dirty}
          onClick={() =>
            void save(guildId, {
              ...draft,
              rewrite_hosts: { ...FIXED_REWRITE_HOSTS },
            })
          }
        >
          {saving ? d.saving : d.saveSettings}
        </Button>
      </PageActionFooter>
    </div>
  );
}

function ChannelChips({
  ids,
  channels,
  onRemove,
  unavailableLabel,
}: {
  ids: string[];
  channels: { id: string; name: string }[];
  onRemove: (id: string) => void;
  unavailableLabel: string;
}) {
  if (!ids.length) return null;
  const names = new Map(channels.map((c) => [c.id, c.name]));
  return (
    <div className="d-flex flex-wrap gap-2 mt-2">
      {ids.map((id) => (
        <Button
          key={id}
          size="sm"
          variant="secondary"
          onClick={() => onRemove(id)}
        >
          #{names.get(id) ?? unavailableLabel} ×
        </Button>
      ))}
    </div>
  );
}
