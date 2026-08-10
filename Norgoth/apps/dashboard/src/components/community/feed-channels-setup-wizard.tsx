"use client";

import { useState } from "react";
import {
  CAlert,
  CFormCheck,
  CFormLabel,
  CFormSelect,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Stepper } from "@/components/ui/stepper";
import { DiscordEmojiPicker } from "@/components/discord/discord-emoji-picker";
import { GuildChannelMultiSelect } from "@/components/ui/guild-channel-multi-select";
import { ChannelSelect } from "@/components/ui/channel-select";
import { NumberInput } from "@/components/ui/number-input";
import type { GuildCategory, GuildChannel } from "@/stores/guild-store";
import type { GuildEmojiItem } from "@/lib/discord/emoji-data";
import { feedEmojiFromPicker, feedEmojiToPicker } from "@/lib/feed-emoji";
import {
  DEFAULT_FEED_CONFIG,
  FEED_WINDOW_LABELS,
  type FeedConfig,
  type FeedWindowKey,
  useFeedChannelsStore,
} from "@/stores/feed-channels-store";

const STEPS = [
  { id: "emojis", label: "Emojis" },
  { id: "sources", label: "Sources" },
  { id: "windows", label: "Feeds" },
  { id: "review", label: "Review" },
];

const WINDOW_KEYS: FeedWindowKey[] = [
  "daily",
  "weekly",
  "monthly",
  "all_time",
];

type Props = {
  guildId: string;
  channels: GuildChannel[];
  categories?: GuildCategory[];
  guildEmojis: GuildEmojiItem[];
  onComplete: () => void;
};

export function FeedChannelsSetupWizard({
  guildId,
  channels,
  categories = [],
  guildEmojis,
  onComplete,
}: Props) {
  const save = useFeedChannelsStore((s) => s.save);
  const setEnabled = useFeedChannelsStore((s) => s.setEnabled);
  const busy = useFeedChannelsStore((s) => s.busy);

  const [step, setStep] = useState(0);
  const [localError, setLocalError] = useState<string | null>(null);
  const [draft, setDraft] = useState<FeedConfig>(() => ({
    ...DEFAULT_FEED_CONFIG,
    windows: {
      daily: { ...DEFAULT_FEED_CONFIG.windows.daily },
      weekly: { ...DEFAULT_FEED_CONFIG.windows.weekly },
      monthly: { ...DEFAULT_FEED_CONFIG.windows.monthly },
      all_time: { ...DEFAULT_FEED_CONFIG.windows.all_time },
    },
  }));

  const textChannels = channels;

  function patch(partial: Partial<FeedConfig>) {
    setDraft((current) => ({ ...current, ...partial }));
  }

  function patchWindow(key: FeedWindowKey, partial: Partial<FeedConfig["windows"][FeedWindowKey]>) {
    setDraft((current) => ({
      ...current,
      windows: {
        ...current.windows,
        [key]: { ...current.windows[key], ...partial },
      },
    }));
  }

  async function finish() {
    setLocalError(null);
    const saved = await save(guildId, { ...draft, enabled: false });
    if (!saved) {
      setLocalError("Could not save Top Trending configuration.");
      return;
    }
    const enabled = await setEnabled(guildId, true);
    if (!enabled) {
      setLocalError("Configuration saved, but enabling Top Trending failed.");
      return;
    }
    onComplete();
  }

  return (
    <Card>
      <div className="d-flex flex-column gap-4">
        <div>
          <h2 className="h5 mb-1">Set up Top Trending</h2>
          <p className="mb-0 text-body-secondary">
            Configure upvote/downvote emojis, source channels, and destination
            feeds for Daily, Weekly, Monthly, and All-Time windows (UTC).
          </p>
        </div>

        <Stepper steps={STEPS} current={step} />

        {localError ? (
          <CAlert color="danger" className="mb-0 py-2">
            {localError}
          </CAlert>
        ) : null}

        {step === 0 ? (
          <div className="d-flex flex-column gap-3">
            <div>
              <CFormLabel>Upvote emoji</CFormLabel>
              <DiscordEmojiPicker
                value={feedEmojiToPicker(draft.upvote_emoji)}
                guildEmojis={guildEmojis}
                onChange={(value) => {
                  const emoji = feedEmojiFromPicker(value);
                  if (emoji) patch({ upvote_emoji: emoji });
                }}
              />
            </div>
            <div>
              <CFormLabel>Downvote emoji</CFormLabel>
              <DiscordEmojiPicker
                value={feedEmojiToPicker(draft.downvote_emoji)}
                guildEmojis={guildEmojis}
                onChange={(value) => {
                  const emoji = feedEmojiFromPicker(value);
                  if (emoji) patch({ downvote_emoji: emoji });
                }}
              />
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="d-flex flex-column gap-3">
            <div>
              <CFormLabel>Source channels</CFormLabel>
              <GuildChannelMultiSelect
                channels={textChannels}
                selectedIds={draft.source_channel_ids}
                onChange={(ids) => patch({ source_channel_ids: ids })}
              />
            </div>
            <div>
              <CFormLabel>Feed category (optional)</CFormLabel>
              <CFormSelect
                value={draft.feed_category_id ?? ""}
                aria-label="Feed category"
                onChange={(event) =>
                  patch({ feed_category_id: event.target.value || null })
                }
              >
                <option value="">No category (top level)</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </CFormSelect>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="d-flex flex-column gap-3">
            {WINDOW_KEYS.map((key) => (
              <div key={key}>
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <CFormLabel className="mb-0">
                    {FEED_WINDOW_LABELS[key]} feed channel
                  </CFormLabel>
                  <Switch
                    checked={draft.windows[key].enabled}
                    disabled={!draft.windows[key].channel_id}
                    onChange={(checked) =>
                      patchWindow(key, { enabled: checked })
                    }
                    aria-label={`Enable ${FEED_WINDOW_LABELS[key]}`}
                  />
                </div>
                <ChannelSelect
                  channels={textChannels}
                  value={draft.windows[key].channel_id ?? ""}
                  onChange={(value) =>
                    patchWindow(key, {
                      channel_id: value || null,
                      enabled: Boolean(value),
                    })
                  }
                  emptyLabel="Select feed channel…"
                />
              </div>
            ))}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="d-flex flex-column gap-3">
            <div className="row g-3">
              <div className="col-md-6">
                <CFormLabel>Minimum net upvotes</CFormLabel>
                <NumberInput
                  value={draft.min_net_score}
                  defaultValue={DEFAULT_FEED_CONFIG.min_net_score}
                  min={0}
                  max={10000}
                  step={1}
                  aria-label="Minimum net upvotes"
                  onCommit={(next) => patch({ min_net_score: next })}
                />
              </div>
              <div className="col-md-6">
                <CFormLabel>Display limit (1–25)</CFormLabel>
                <NumberInput
                  value={draft.display_limit}
                  defaultValue={DEFAULT_FEED_CONFIG.display_limit}
                  min={1}
                  max={25}
                  step={1}
                  aria-label="Display limit"
                  onCommit={(next) => patch({ display_limit: next })}
                />
              </div>
            </div>
            <CFormCheck
              label="Exclude bots"
              checked={draft.exclude_bots}
              onChange={(e) => patch({ exclude_bots: e.target.checked })}
            />
            <CAlert color="secondary" className="mb-0">
              Enabling Top Trending will track messages in{" "}
              <strong>{draft.source_channel_ids.length}</strong> source channel
              {draft.source_channel_ids.length === 1 ? "" : "s"} and publish
              ranked embeds to configured Top Trending channels. All windows are UTC.
            </CAlert>
          </div>
        ) : null}

        <div className="d-flex justify-content-between gap-2">
          <Button
            variant="secondary"
            disabled={step === 0 || busy}
            onClick={() => {
              setLocalError(null);
              setStep((s) => Math.max(0, s - 1));
            }}
          >
            Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => {
                setLocalError(null);
                setStep((s) => Math.min(STEPS.length - 1, s + 1));
              }}
            >
              Next
            </Button>
          ) : (
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => void finish()}
            >
              {busy ? "Saving…" : "Enable Top Trending"}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
