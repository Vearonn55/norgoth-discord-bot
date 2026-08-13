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
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useAutoResponsesStore,
  type MatchType,
} from "@/stores/automation-store";

export function AutoResponsesPanel() {
  const dict = useLocaleDict();
  const d = dict.autoResponsesPage;
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

  const matchLabels: Record<MatchType, string> = useMemo(
    () => ({
      exact: d.matchLabelExact,
      contains: d.matchLabelContains,
      starts_with: d.matchLabelStartsWith,
    }),
    [d.matchLabelExact, d.matchLabelContains, d.matchLabelStartsWith],
  );

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
          {d.loading}
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">{d.botRequired}</Badge>
          <p className="small text-body-secondary">{error}</p>
          <Button variant="secondary" onClick={() => void reload()}>
            {d.retry}
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
            <h2 className="h5 mb-0 fw-semibold">{d.newRuleTitle}</h2>
            <p className="mt-1 small text-body-secondary">{d.newRuleDesc}</p>
          </div>

          <div className="row g-3">
            <div>
              <CFormLabel>{d.matchType}</CFormLabel>
              <CFormSelect
                value={draft.match_type}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    match_type: event.target.value as MatchType,
                  }))
                }
              >
                <option value="contains">{d.matchContains}</option>
                <option value="exact">{d.matchExact}</option>
                <option value="starts_with">{d.matchStartsWith}</option>
              </CFormSelect>
            </div>

            <div className="col-md-8">
              <CFormLabel>{d.triggerText}</CFormLabel>
              <CFormInput
                value={draft.trigger}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    trigger: event.target.value,
                  }))
                }
                maxLength={200}
                placeholder={d.triggerPlaceholder}
              />
            </div>
          </div>

          <div>
            <CFormLabel>{d.response}</CFormLabel>
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
              placeholder={d.responsePlaceholder}
            />
            <p className="mt-1 mb-0 small text-body-secondary">
              {formatDict(d.charCount, { count: draft.response.length })}
            </p>
          </div>

          <div className="row g-3">
            <div>
              <CFormLabel>{d.restrictChannel}</CFormLabel>
              <CFormSelect
                value={draft.channel_id ?? ""}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    channel_id: event.target.value || null,
                  }))
                }
              >
                <option value="">{d.anyChannel}</option>
                {channels.map((channel) => (
                  <option key={channel.id} value={channel.id}>
                    #{channel.name}
                  </option>
                ))}
              </CFormSelect>
            </div>

            <div>
              <CFormLabel>{d.cooldown}</CFormLabel>
              <NumberInput
                value={draft.cooldown_seconds}
                defaultValue={0}
                min={0}
                max={3600}
                step={1}
                aria-label={d.cooldownAria}
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
              {saving ? d.saving : d.addRule}
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
              <h2 className="h5 mb-0 fw-semibold">{d.activeRules}</h2>
              <p className="mt-1 small text-body-secondary">
                {formatDict(d.rulesCount, { count: rules.length })}
              </p>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => void load(guildId)}
            >
              {d.refresh}
            </Button>
          </div>

          {rules.length === 0 ? (
            <p className="border rounded p-5 small text-body-secondary">
              {d.emptyRules}
            </p>
          ) : (
            <DataTable
              columns={[
                {
                  key: "enabled",
                  header: d.colOn,
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
                      aria-label={formatDict(d.enableRuleAria, {
                        trigger: row.trigger,
                      })}
                    />
                  ),
                },
                {
                  key: "trigger",
                  header: d.colTrigger,
                  cell: (row) => (
                    <span>
                      {formatDict(d.triggerSummary, {
                        match: matchLabels[row.match_type],
                        trigger: row.trigger,
                      })}
                    </span>
                  ),
                },
                {
                  key: "response",
                  header: d.colResponse,
                  cell: (row) => (
                    <span className="line-clamp-2 text-body-secondary">
                      {row.response}
                    </span>
                  ),
                },
                {
                  key: "channel",
                  header: d.colChannel,
                  cell: (row) =>
                    row.channel_id
                      ? `#${channelNames.get(row.channel_id) ?? row.channel_id}`
                      : d.any,
                },
                {
                  key: "cooldown",
                  header: d.colCooldown,
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
                      {d.delete}
                    </Button>
                  ),
                },
              ]}
              rows={filteredRules}
              rowKey={(row) => row.id}
              emptyMessage={d.emptyMatching}
              search={search}
              onSearchChange={setSearch}
              searchPlaceholder={d.searchPlaceholder}
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
