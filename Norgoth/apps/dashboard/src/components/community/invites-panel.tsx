"use client";

import { useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { CAlert, CSpinner } from "@coreui/react";
import {
  cilLink,
  cilPeople,
  cilUserFollow,
} from "@coreui/icons";
import { TrendChart } from "@/components/analytics/trend-chart";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CategoryHeader } from "@/components/ui/category-header";
import { DataTable } from "@/components/ui/data-table";
import {
  DateRangePicker,
  isInDateRange,
} from "@/components/ui/date-range-filter";
import { Icon } from "@/components/ui/icon";
import { SectionCard } from "@/components/ui/section-card";
import { formatDateTime } from "@/lib/datetime";
import { invitedByLabel, invitationSourceLabel } from "@/lib/invite-attribution";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useFirstGuild } from "@/lib/use-first-guild";
import { useInvitesStore } from "@/stores/invites-store";

export function InvitesPanel() {
  const dict = useLocaleDict();
  const d = dict.invitesPage;
  const params = useParams();
  const lang = String(params?.lang || "en");
  const { guildId, loading, error, reload } = useFirstGuild();

  const leaderboard = useInvitesStore((s) => s.leaderboard);
  const recent = useInvitesStore((s) => s.recent);
  const loadError = useInvitesStore((s) => s.loadError);
  const leaderboardSearch = useInvitesStore((s) => s.leaderboardSearch);
  const leaderboardPage = useInvitesStore((s) => s.leaderboardPage);
  const recentSearch = useInvitesStore((s) => s.recentSearch);
  const recentPage = useInvitesStore((s) => s.recentPage);
  const dateRange = useInvitesStore((s) => s.dateRange);
  const setLeaderboardSearch = useInvitesStore((s) => s.setLeaderboardSearch);
  const setLeaderboardPage = useInvitesStore((s) => s.setLeaderboardPage);
  const setRecentSearch = useInvitesStore((s) => s.setRecentSearch);
  const setRecentPage = useInvitesStore((s) => s.setRecentPage);
  const setDateRange = useInvitesStore((s) => s.setDateRange);
  const load = useInvitesStore((s) => s.load);

  useEffect(() => {
    if (!guildId) return;
    void load(guildId);
  }, [guildId, load]);

  const filteredLeaderboard = useMemo(() => {
    const query = leaderboardSearch.trim().toLowerCase();
    if (!query) return leaderboard;
    return leaderboard.filter((entry) =>
      entry.name.toLowerCase().includes(query)
    );
  }, [leaderboard, leaderboardSearch]);

  const filteredRecent = useMemo(() => {
    const query = recentSearch.trim().toLowerCase();
    return recent.filter((entry) => {
      if (!isInDateRange(entry.joined_at, dateRange)) return false;
      if (!query) return true;
      return [
        entry.member_name,
        entry.inviter_name ?? "",
        entry.inviter_id ?? "",
        entry.attribution ?? "",
        entry.code ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [recent, recentSearch, dateRange]);

  const inviteTrend = useMemo(() => {
    const map = new Map<
      string,
      { date: string; joins: number; rejoins: number; leaves: number }
    >();
    for (const entry of recent) {
      if (!isInDateRange(entry.joined_at, dateRange)) continue;
      const day = entry.joined_at.slice(0, 10);
      const current = map.get(day) ?? {
        date: day.slice(5),
        joins: 0,
        rejoins: 0,
        leaves: 0,
      };
      if (entry.rejoin) current.rejoins += 1;
      else current.joins += 1;
      if (entry.left_at) current.leaves += 1;
      map.set(day, current);
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([, v]) => v);
  }, [recent, dateRange]);

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
          <p className="mb-0 small text-body-secondary">{error}</p>
          <div>
            <Button variant="secondary" onClick={() => void reload()}>
              {d.retry}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="d-flex flex-column gap-3">
      {loadError ? (
        <CAlert color="danger" className="mb-0">
          {loadError}
        </CAlert>
      ) : null}

      <CategoryHeader
        category="invitations"
        title={d.trendsTitle}
        description={d.trendsDesc}
        as="h2"
        actions={
          <DateRangePicker value={dateRange} onChange={setDateRange} />
        }
      />

      <SectionCard level="primary" category="invitations">
        <TrendChart
          data={inviteTrend}
          xKey="date"
          series={[
            { key: "joins", label: d.seriesJoins, color: "#3dd68c" },
            { key: "rejoins", label: d.seriesRejoins, color: "#fbbf24" },
            { key: "leaves", label: d.seriesLeaves, color: "#ff6b7a" },
          ]}
          emptyMessage={d.emptyTrend}
        />
      </SectionCard>

      <SectionCard
        level="primary"
        category="invitations"
        header={
          <div className="d-flex align-items-center justify-content-between gap-3">
            <div className="d-flex align-items-start gap-3">
              <Icon
                icon={cilLink}
                size="lg"
                className="text-body-secondary mt-1"
              />
              <div>
                <h2 className="h5 mb-0 fw-semibold">{d.leaderboardTitle}</h2>
                <p className="mt-1 mb-0 small text-body-secondary">
                  {d.leaderboardDesc}
                </p>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void load(guildId)}
            >
              {d.refresh}
            </Button>
          </div>
        }
      >
        {leaderboard.length === 0 ? (
          <CAlert color="secondary" className="mb-0">
            {d.emptyLeaderboard}
          </CAlert>
        ) : (
          <DataTable
            columns={[
              {
                key: "rank",
                header: "#",
                className: "w-auto",
                cell: (row) => `#${row.rank}`,
              },
              {
                key: "name",
                header: d.colMember,
                cell: (row) => row.name,
              },
              {
                key: "net",
                header: d.colNet,
                cell: (row) => (
                  <Badge variant="success">
                    {formatDict(d.netInvites, { count: row.net })}
                  </Badge>
                ),
              },
              {
                key: "joins",
                header: d.colJoins,
                cell: (row) => row.joins,
              },
              {
                key: "leaves",
                header: d.colLeft,
                cell: (row) => row.leaves,
              },
              {
                key: "rejoins",
                header: d.colRejoins,
                cell: (row) => row.rejoins,
              },
            ]}
            rows={filteredLeaderboard}
            rowKey={(row) => row.inviter_id}
            emptyMessage={d.emptyMatchingInviters}
            search={leaderboardSearch}
            onSearchChange={setLeaderboardSearch}
            searchPlaceholder={d.searchInviters}
            page={leaderboardPage}
            pageSize={10}
            onPageChange={setLeaderboardPage}
          />
        )}
      </SectionCard>

      <SectionCard
        level="secondary"
        category="community"
        header={
          <div className="d-flex align-items-start gap-3">
            <Icon
              icon={cilUserFollow}
              size="lg"
              className="text-body-secondary mt-1"
            />
            <div>
              <h2 className="h5 mb-0 fw-semibold">{d.recentTitle}</h2>
              <p className="mt-1 mb-0 small text-body-secondary">
                {d.recentDesc}
              </p>
            </div>
          </div>
        }
      >
        {recent.length === 0 ? (
          <CAlert color="secondary" className="mb-0">
            {d.emptyRecent}
          </CAlert>
        ) : (
          <DataTable
            columns={[
              {
                key: "member",
                header: d.colMember,
                cell: (row) => row.member_name,
              },
              {
                key: "inviter",
                header: d.colInvitedBy,
                cell: (row) => invitedByLabel(row, d),
              },
              {
                key: "code",
                header: d.colCode,
                cell: (row) => invitationSourceLabel(row, d),
              },
              {
                key: "flags",
                header: d.colFlags,
                cell: (row) => (
                  <span className="d-flex flex-wrap gap-2">
                    {!row.rejoin ? (
                      <Badge variant="success">{d.flagFirstJoin}</Badge>
                    ) : (
                      <Badge variant="warning">{d.flagRejoin}</Badge>
                    )}
                    {row.left_at ? (
                      <Badge variant="danger">{d.flagLeft}</Badge>
                    ) : null}
                  </span>
                ),
              },
              {
                key: "when",
                header: d.colJoined,
                className: "text-nowrap",
                cell: (row) => formatDateTime(row.joined_at, lang),
              },
            ]}
            rows={filteredRecent}
            rowKey={(row) =>
              `${row.joined_at}-${row.member_name}-${row.code ?? ""}`
            }
            emptyMessage={d.emptyMatchingJoins}
            search={recentSearch}
            onSearchChange={setRecentSearch}
            searchPlaceholder={d.searchJoins}
            page={recentPage}
            pageSize={10}
            onPageChange={setRecentPage}
            toolbar={
              <div className="d-flex align-items-center gap-2 small text-body-secondary">
                <Icon icon={cilPeople} />
                {formatDict(d.inRange, { count: filteredRecent.length })}
              </div>
            }
          />
        )}
      </SectionCard>
    </div>
  );
}
