"use client";

import { useEffect, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CButton, CButtonGroup } from "@coreui/react";
import { CategoryHeader } from "@/components/ui/category-header";
import { SectionCard } from "@/components/ui/section-card";
import {
  computeEngagementMetrics,
  percentDelta,
  type EngagementRange,
} from "@/lib/analytics/engagement";
import { useDashboardStore } from "@/stores/dashboard-store";
import { useGuildStore } from "@/stores/guild-store";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

const RANGES: EngagementRange[] = [7, 30, 90];

export function EngagementChart() {
  const dict = useLocaleDict();
  const d = dict.dashboard;
  const guildId = useGuildStore((s) => s.guildId);
  const memberCount = useGuildStore((s) => s.resources?.member_count ?? null);
  const engagement = useDashboardStore((s) => s.engagement);
  const engagementRange = useDashboardStore((s) => s.engagementRange);
  const engagementLoading = useDashboardStore((s) => s.engagementLoading);
  const loadEngagement = useDashboardStore((s) => s.loadEngagement);
  const setEngagementRange = useDashboardStore((s) => s.setEngagementRange);

  useEffect(() => {
    if (!guildId) return;
    void loadEngagement(guildId, engagementRange);
  }, [guildId, engagementRange, loadEngagement]);

  const metrics = useMemo(() => {
    if (!engagement || engagement.insufficient_history) return null;
    return computeEngagementMetrics(engagement.totals, memberCount);
  }, [engagement, memberCount]);

  const previousMetrics = useMemo(() => {
    if (!engagement || engagement.insufficient_history) return null;
    return computeEngagementMetrics(engagement.previous_totals, memberCount);
  }, [engagement, memberCount]);

  const scoreDelta =
    metrics && previousMetrics
      ? percentDelta(metrics.score, previousMetrics.score)
      : null;

  const chartData = useMemo(() => {
    if (!engagement) return [];
    return engagement.series.map((point) => ({
      date: point.date.slice(5),
      messages: point.messages,
      authors: point.unique_authors,
      voice: point.voice_uniques,
      joins: point.joins,
    }));
  }, [engagement]);

  return (
    <SectionCard level="primary" category="analytics" className="h-100">
      <CategoryHeader
        category="analytics"
        title={d.engagementTitle}
        description={d.engagementDescription}
        as="h3"
        actions={
          <CButtonGroup size="sm" aria-label={d.engagementRangeAria}>
            {RANGES.map((range) => (
              <CButton
                key={range}
                type="button"
                color={engagementRange === range ? "primary" : "secondary"}
                variant={engagementRange === range ? undefined : "outline"}
                onClick={() => setEngagementRange(range)}
              >
                {range}d
              </CButton>
            ))}
          </CButtonGroup>
        }
      />

      {!guildId ? (
        <p className="mb-0 small text-body-secondary">{d.engagementNoGuild}</p>
      ) : engagementLoading && !engagement ? (
        <p className="mb-0 small text-body-secondary">{d.engagementLoading}</p>
      ) : engagement?.insufficient_history ? (
        <div className="norgoth-empty-state py-4 text-center">
          <p className="mb-1 fw-semibold">{d.engagementNoHistoryTitle}</p>
          <p className="mb-0 small text-body-secondary">
            {d.engagementNoHistoryBody}
          </p>
        </div>
      ) : (
        <>
          <div className="d-flex flex-wrap align-items-end gap-3 mb-3">
            <div>
              <div className="small text-body-secondary text-uppercase fw-semibold">
                {d.engagementScore}
              </div>
              <div className="display-6 fw-semibold lh-1 text-white">
                {metrics ? Math.round(metrics.score) : "—"}
              </div>
            </div>
            {scoreDelta != null ? (
              <span
                className={`small fw-semibold ${
                  scoreDelta >= 0 ? "text-success" : "text-danger"
                }`}
              >
                {formatDict(d.engagementVsPrior, {
                  delta: `${scoreDelta >= 0 ? "+" : ""}${scoreDelta.toFixed(1)}`,
                  days: engagementRange,
                })}
              </span>
            ) : (
              <span className="small text-body-secondary">
                {d.engagementPriorUnavailable}
              </span>
            )}
            <div className="ms-auto d-flex flex-wrap gap-3 small text-body-secondary">
              <span>
                {formatDict(d.engagementMsgs, {
                  count: engagement?.totals.messages ?? 0,
                })}
              </span>
              <span>
                {formatDict(d.engagementAuthors, {
                  count: engagement?.totals.unique_authors ?? 0,
                })}
              </span>
              <span>
                {formatDict(d.engagementJoins, {
                  count: engagement?.totals.joins ?? 0,
                })}
              </span>
              <span>
                {formatDict(d.engagementVoice, {
                  count: engagement?.totals.voice_uniques ?? 0,
                })}
              </span>
            </div>
          </div>

          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="engMsg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6ea8fe" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#6ea8fe" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(241,244,250,0.08)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "rgba(241,244,250,0.55)", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "rgba(241,244,250,0.55)", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={36}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a2230",
                    border: "1px solid rgba(241,244,250,0.2)",
                    borderRadius: 8,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="messages"
                  name={d.chartMessages}
                  stroke="#6ea8fe"
                  fill="url(#engMsg)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="authors"
                  name={d.chartAuthors}
                  stroke="#3dd68c"
                  fill="transparent"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </SectionCard>
  );
}
