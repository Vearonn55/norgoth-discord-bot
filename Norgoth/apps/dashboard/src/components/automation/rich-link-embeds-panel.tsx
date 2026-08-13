"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  CAlert,
  CFormCheck,
  CFormInput,
  CFormLabel,
  CSpinner,
} from "@coreui/react";
import { SectionCard } from "@/components/ui/section-card";
import { ChannelSelect } from "@/components/ui/channel-select";
import { Button } from "@/components/ui/button";
import { NumberInput } from "@/components/ui/number-input";
import { MiniFeatureCard } from "@/components/ui/mini-feature-card";
import { MutedSection } from "@/components/ui/feature-muting";
import { PageHeader } from "@/components/layout/page-header";
import { PageActionFooter } from "@/components/layout/page-action-footer";
import { useFirstGuild } from "@/stores/guild-store";
import {
  defaults,
  useRichLinkEmbedsStore,
  type RichLinkEmbedsConfig,
  type RichLinkPlatforms,
} from "@/stores/rich-link-embeds-store";
import { Icon } from "@/components/ui/icon";
import { cilBell, cilImage, cilLink, cilShare } from "@coreui/icons";
import { useFeatureInfo } from "@/lib/feature-info";

const PLATFORM_META: {
  key: keyof RichLinkPlatforms;
  name: string;
  description: string;
  icon: string | string[];
}[] = [
  {
    key: "twitter",
    name: "Twitter / X",
    description: "Status links → embed-friendly host",
    icon: cilShare,
  },
  {
    key: "bluesky",
    name: "Bluesky",
    description: "Profile post links → embed-friendly host",
    icon: cilBell,
  },
  {
    key: "tiktok",
    name: "TikTok",
    description: "Video links → embed-friendly host",
    icon: cilImage,
  },
  {
    key: "reddit",
    name: "Reddit",
    description: "Post / short links → embed-friendly host",
    icon: cilLink,
  },
];

function previewRewrite(
  url: string,
  config: RichLinkEmbedsConfig,
): string | null {
  try {
    const parsed = new URL(url.trim());
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    let host = parsed.hostname.toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);

    const rules: {
      key: keyof RichLinkPlatforms;
      suffixes: string[];
      pathTokens: string[];
    }[] = [
      {
        key: "twitter",
        suffixes: ["twitter.com", "x.com"],
        pathTokens: ["/status/"],
      },
      {
        key: "bluesky",
        suffixes: ["bsky.app"],
        pathTokens: ["/profile/", "/post/"],
      },
      {
        key: "tiktok",
        suffixes: ["tiktok.com"],
        pathTokens: ["/video/", "/t/"],
      },
      { key: "reddit", suffixes: ["reddit.com", "redd.it"], pathTokens: [] },
    ];

    for (const rule of rules) {
      if (!config.platforms[rule.key]) continue;
      const match = rule.suffixes.some(
        (suffix) => host === suffix || host.endsWith(`.${suffix}`),
      );
      if (!match) continue;
      if (
        rule.pathTokens.length > 0 &&
        !rule.pathTokens.some((token) => parsed.pathname.includes(token))
      ) {
        continue;
      }
      const rewriteHost =
        config.rewrite_hosts[rule.key] || defaults.rewrite_hosts[rule.key];
      return `${parsed.protocol}//${rewriteHost}${parsed.pathname}`;
    }
    return null;
  } catch {
    return null;
  }
}

export function RichLinkEmbedsPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const isTr = lang === "tr";
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
        <CSpinner size="sm" />{" "}
        {isTr
          ? "Zengin bağlantı ayarları yükleniyor…"
          : "Loading rich link embeds…"}
      </div>
    );
  }

  if (!guildId) {
    return (
      <p className="text-body-secondary">
        {isTr ? "Önce bir sunucu seçin." : "Select a server first."}
      </p>
    );
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
    const next = { ...draft, enabled: checked };
    setDraft(next);
    await save(guildId, next);
  }

  const dirty = JSON.stringify(draft) !== JSON.stringify(config);
  const disclosureHosts = Object.values(draft.rewrite_hosts).join(", ");

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={info?.title ?? "Rich Link Embeds"}
        category="messages"
        icon={<Icon icon={cilLink} size="xl" />}
        description={
          info?.description ??
          "Reply with embed-friendly social media links without editing member messages."
        }
        infoKey="richLinkEmbeds"
        masterToggle={{
          enabled: draft.enabled,
          onChange: (checked) => void setEnabledAndSave(checked),
          loading: saving,
          label: "Rich Link Embeds",
          showLabel: false,
        }}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      <MutedSection enabled={draft.enabled} className="d-flex flex-column gap-4">
        <SectionCard
          level="primary"
          category="messages"
          header={isTr ? "Platformlar" : "Platforms"}
        >
          <div className="d-flex flex-wrap gap-3 p-1">
            {PLATFORM_META.map((platform) => (
              <div key={platform.key} style={{ minWidth: 260, flex: "1 1 260px" }}>
                <MiniFeatureCard
                  icon={platform.icon}
                  name={platform.name}
                  description={platform.description}
                  category="messages"
                  enabled={draft.platforms[platform.key]}
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

        <SectionCard
          level="secondary"
          category="messages"
          header={isTr ? "Kanallar" : "Channels"}
        >
          <div className="d-flex flex-column gap-3 p-1">
            <div>
              <CFormLabel>
                {isTr ? "İzin listesi (boş = tümü)" : "Allowlist (empty = all)"}
              </CFormLabel>
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
              <CFormLabel>{isTr ? "Engellenen kanallar" : "Denylist"}</CFormLabel>
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

        <SectionCard
          level="secondary"
          category="messages"
          header={isTr ? "Davranış" : "Behavior"}
        >
          <div className="d-flex flex-column gap-3 p-1">
            <CFormCheck
              id="rle-ignore-bots"
              label={isTr ? "Bot mesajlarını yok say" : "Ignore bot messages"}
              checked={draft.ignore_bots}
              onChange={(e) => patch({ ignore_bots: e.target.checked })}
            />
            <CFormCheck
              id="rle-process-edits"
              label={
                isTr
                  ? "Düzenlenen mesajları işle"
                  : "Also process message edits"
              }
              checked={draft.process_edits}
              onChange={(e) => patch({ process_edits: e.target.checked })}
            />
            <div style={{ maxWidth: 240 }}>
              <CFormLabel>
                {isTr
                  ? "Mesaj başına en fazla bağlantı"
                  : "Max links per message"}
              </CFormLabel>
              <NumberInput
                value={draft.max_links_per_message}
                min={1}
                max={10}
                onCommit={(next) => patch({ max_links_per_message: next })}
              />
            </div>
          </div>
        </SectionCard>

        <SectionCard
          level="secondary"
          category="messages"
          header={isTr ? "Gizlilik bildirimi" : "External service disclosure"}
        >
          <div className="d-flex flex-column gap-3 p-1">
            <CAlert color="info" className="mb-0">
              {isTr
                ? `Yeniden yazılan bağlantılar üçüncü taraf gömme hizmetlerine yönlendirir (${disclosureHosts}). Bu alan adları NorBot tarafından işletilmez; kullanılabilirlik ve gizlilik politikaları değişebilir.`
                : `Rewritten links point to third-party embed fixer domains (${disclosureHosts}). These hosts are not operated by NorBot; availability and privacy policies may change.`}
            </CAlert>
            <CFormCheck
              id="rle-disclosure"
              label={
                isTr
                  ? "Üçüncü taraf alan adlarının kullanıldığını anlıyorum"
                  : "I understand external fixer domains are used"
              }
              checked={draft.disclosure_acknowledged}
              onChange={(e) =>
                patch({ disclosure_acknowledged: e.target.checked })
              }
            />
          </div>
        </SectionCard>

        <SectionCard
          level="secondary"
          category="messages"
          header={isTr ? "Bağlantı testi" : "Test URL"}
        >
          <div className="d-flex flex-column gap-2 p-1">
            <CFormLabel>
              {isTr
                ? "Yeniden yazmayı önizlemek için bir URL yapıştırın"
                : "Paste a URL to preview the rewrite (client-side only)"}
            </CFormLabel>
            <CFormInput
              value={testUrl}
              onChange={(e) => setTestUrl(e.target.value)}
              placeholder="https://x.com/user/status/123"
            />
            {testUrl.trim() ? (
              <p className="small mb-0 text-body-secondary">
                {preview
                  ? `${isTr ? "Önizleme" : "Preview"}: ${preview}`
                  : isTr
                    ? "Eşleşen platform yok veya platform kapalı."
                    : "No matching enabled platform."}
              </p>
            ) : null}
          </div>
        </SectionCard>
      </MutedSection>

      <PageActionFooter>
        <Button
          variant="primary"
          disabled={saving || !draft.enabled || !dirty}
          onClick={() => void save(guildId, draft)}
        >
          {saving
            ? isTr
              ? "Kaydediliyor…"
              : "Saving…"
            : isTr
              ? "Ayarları kaydet"
              : "Save Settings"}
        </Button>
      </PageActionFooter>
    </div>
  );
}

function ChannelChips({
  ids,
  channels,
  onRemove,
}: {
  ids: string[];
  channels: { id: string; name: string }[];
  onRemove: (id: string) => void;
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
          #{names.get(id) ?? id} ×
        </Button>
      ))}
    </div>
  );
}
