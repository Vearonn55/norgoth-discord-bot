"use client";

import { useEffect, useMemo } from "react";
import {
  CFormInput,
  CFormLabel,
  CFormSelect,
  CSpinner,
} from "@coreui/react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { NumberInput } from "@/components/ui/number-input";
import { DataTable } from "@/components/ui/data-table";
import { RichMessageEditor } from "@/components/editors/rich-message-editor";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useAutoResponsesStore,
  type MatchType,
} from "@/stores/automation-store";

const MATCH_LABELS: Record<MatchType, string> = {
  exact: "is exactly",
  contains: "contains",
  starts_with: "starts with",
};

export function AutoResponsesPanel() {
  const { guildId, resources, loading, error, reload } = useFirstGuild();

  const rules = useAutoResponsesStore((s) => s.rules);
  const draft = useAutoResponsesStore((s) => s.draft);
  const saving = useAutoResponsesStore((s) => s.saving);
  const feedback = useAutoResponsesStore((s) => s.feedback);
  const feedbackIsError = useAutoResponsesStore((s) => s.feedbackIsError);
  const search = useAutoResponsesStore((s) => s.search);
  const page = useAutoResponsesStore((s) => s.page);
  const setDraft = useAutoResponsesStore((s) => s.setDraft);
  const setSearch = useAutoResponsesStore((s) => s.setSearch);
  const setPage = useAutoResponsesStore((s) => s.setPage);
  const load = useAutoResponsesStore((s) => s.load);
  const persist = useAutoResponsesStore((s) => s.persist);
  const addRule = useAutoResponsesStore((s) => s.addRule);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  const channels = useMemo(() => resources?.channels ?? [], [resources]);
  const channelNames = useMemo(
    () => new Map(channels.map((channel) => [channel.id, channel.name])),
    [channels]
  );

  const filteredRules = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return rules;
    return rules.filter((rule) =>
      [
        rule.trigger,
        rule.response,
        rule.match_type,
        rule.channel_id
          ? channelNames.get(rule.channel_id) ?? rule.channel_id
          : "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [rules, search, channelNames]);

  if (loading) {
    return (
      <Card>
        <div className="d-flex align-items-center gap-2 text-body-secondary">
          <CSpinner size="sm" />
          Loading auto-responses…
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

  return (
    <div className="d-flex flex-column gap-4">
      <Card>
        <div className="d-flex flex-column gap-3">
          <div>
            <h2 className="h5 mb-0 fw-semibold">New Response Rule</h2>
            <p className="mt-1 small text-body-secondary">
              When a message matches the trigger, the bot replies in the same
              channel. Variables: {"{user}"}, {"{username}"}, {"{server}"}.
            </p>
          </div>

          <div className="row g-3">
            <div>
              <CFormLabel>Match type</CFormLabel>
              <CFormSelect
                value={draft.match_type}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    match_type: event.target.value as MatchType,
                  }))
                }
              >
                <option value="contains">Message contains</option>
                <option value="exact">Message is exactly</option>
                <option value="starts_with">Message starts with</option>
              </CFormSelect>
            </div>

            <div className="col-md-8">
              <CFormLabel>Trigger text</CFormLabel>
              <CFormInput
                value={draft.trigger}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    trigger: event.target.value,
                  }))
                }
                maxLength={200}
                placeholder="e.g. how do I verify"
              />
            </div>
          </div>

          <div>
            <CFormLabel>Response</CFormLabel>
            <RichMessageEditor
              key={`auto-response-${draft.trigger}-${rules.length}`}
              value={draft.response}
              onChange={(markdown) =>
                setDraft((current) => ({
                  ...current,
                  response: markdown,
                }))
              }
              variables={["{user}", "{username}", "{server}"]}
              height={180}
              placeholder="e.g. Hi {user}, head to #verification to get started!"
            />
            <p className="mt-1 mb-0 small text-body-secondary">
              {draft.response.length}/1500 characters
            </p>
          </div>

          <div className="row g-3">
            <div>
              <CFormLabel>Restrict to channel (optional)</CFormLabel>
              <CFormSelect
                value={draft.channel_id ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    channel_id: event.target.value || null,
                  }))
                }
              >
                <option value="">Any channel</option>
                {channels.map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    #{channel.name}
                  </option>
                ))}
              </CFormSelect>
            </div>

            <div>
              <CFormLabel>Cooldown (seconds)</CFormLabel>
              <NumberInput
                value={draft.cooldown_seconds}
                defaultValue={0}
                min={0}
                max={3600}
                step={1}
                aria-label="Cooldown seconds"
                onCommit={(next) =>
                  setDraft((current) => ({
                    ...current,
                    cooldown_seconds: next,
                  }))
                }
              />
            </div>
          </div>

          <div className="d-flex align-items-center gap-3">
            <Button
              variant="primary"
              onClick={() => void addRule(guildId)}
              disabled={saving}
            >
              {saving ? "Saving…" : "Add Rule"}
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
              <h2 className="h5 mb-0 fw-semibold">Active Rules</h2>
              <p className="mt-1 small text-body-secondary">
                {rules.length} / 50 rules. Only the first matching rule fires
                per message.
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

          {rules.length === 0 ? (
            <p className="border rounded p-5 small text-body-secondary">
              No response rules yet. Add one above.
            </p>
          ) : (
            <DataTable
              columns={[
                {
                  key: "enabled",
                  header: "On",
                  className: "w-20",
                  cell: (row) => (
                    <Switch
                      checked={row.enabled}
                      onChange={(checked) =>
                        void persist(
                          guildId,
                          rules.map((item) =>
                            item.id === row.id
                              ? { ...item, enabled: checked }
                              : item
                          )
                        )
                      }
                      aria-label={`Enable rule ${row.trigger}`}
                    />
                  ),
                },
                {
                  key: "trigger",
                  header: "Trigger",
                  cell: (row) => (
                    <span>
                      Message {MATCH_LABELS[row.match_type]} “{row.trigger}”
                    </span>
                  ),
                },
                {
                  key: "response",
                  header: "Response",
                  cell: (row) => (
                    <span className="line-clamp-2 text-body-secondary">
                      {row.response}
                    </span>
                  ),
                },
                {
                  key: "channel",
                  header: "Channel",
                  cell: (row) =>
                    row.channel_id
                      ? `#${channelNames.get(row.channel_id) ?? row.channel_id}`
                      : "Any",
                },
                {
                  key: "cooldown",
                  header: "Cooldown",
                  cell: (row) =>
                    row.cooldown_seconds > 0
                      ? `${row.cooldown_seconds}s`
                      : "—",
                },
                {
                  key: "actions",
                  header: "",
                  className: "w-28 text-right",
                  cell: (row) => (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        void persist(
                          guildId,
                          rules.filter((item) => item.id !== row.id)
                        )
                      }
                    >
                      Delete
                    </Button>
                  ),
                },
              ]}
              rows={filteredRules}
              rowKey={(row) => row.id}
              emptyMessage="No matching rules."
              search={search}
              onSearchChange={setSearch}
              searchPlaceholder="Search rules…"
              page={page}
              pageSize={10}
              onPageChange={setPage}
            />
          )}
        </div>
      </Card>
    </div>
  );
}
