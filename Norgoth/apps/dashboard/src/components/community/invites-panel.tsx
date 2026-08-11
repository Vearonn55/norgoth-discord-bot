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
import { useFirstGuild } from "@/lib/use-first-guild";
import { useInvitesStore } from "@/stores/invites-store";

export function InvitesPanel() {
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
      return [entry.member_name, entry.inviter_name ?? "", entry.code ?? ""]
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
          Loading invite tracking…
        </div>
      </Card>
    );
  }

  if (error || !guildId) {
    return (
      <Card>
        <div className="d-flex flex-column gap-3">
          <Badge variant="warning">Bot required</Badge>
          <p className="mb-0 small text-body-secondary">{error}</p>
          <div>
            <Button variant="secondary" onClick={() => void reload()}>
              Retry
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
        title="Invite trends"
        description="Joins, rejoins, and leaves aggregated from recent invite attribution."
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
            { key: "joins", label: "First joins", color: "#3dd68c" },
            { key: "rejoins", label: "Rejoins", color: "#fbbf24" },
            { key: "leaves", label: "Leaves", color: "#ff6b7a" },
          ]}
          emptyMessage="No join events in this date range yet."
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
                <h2 className="h5 mb-0 fw-semibold">Invite Leaderboard</h2>
                <p className="mt-1 mb-0 small text-body-secondary">
                  Net invites = joins − members who left.
                </p>
              </div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void load(guildId)}
            >
              Refresh
            </Button>
          </div>
        }
      >
        {leaderboard.length === 0 ? (
          <CAlert color="secondary" className="mb-0">
            No invite data yet. Attribution starts as members join while the bot
            is online.
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
                header: "Member",
                cell: (row) => row.name,
              },
              {
                key: "net",
                header: "Net",
                cell: (row) => (
                  <Badge variant="success">{row.net} invites</Badge>
                ),
              },
              {
                key: "joins",
                header: "Joins",
                cell: (row) => row.joins,
              },
              {
                key: "leaves",
                header: "Left",
                cell: (row) => row.leaves,
              },
              {
                key: "rejoins",
                header: "Rejoins",
                cell: (row) => row.rejoins,
              },
            ]}
            rows={filteredLeaderboard}
            rowKey={(row) => row.inviter_id}
            emptyMessage="No matching inviters."
            search={leaderboardSearch}
            onSearchChange={setLeaderboardSearch}
            searchPlaceholder="Search inviters…"
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
              <h2 className="h5 mb-0 fw-semibold">Recent Joins</h2>
              <p className="mt-1 mb-0 small text-body-secondary">
                Latest joins with invite attribution.
              </p>
            </div>
          </div>
        }
      >
        {recent.length === 0 ? (
          <CAlert color="secondary" className="mb-0">
            No joins recorded yet.
          </CAlert>
        ) : (
          <DataTable
            columns={[
              {
                key: "member",
                header: "Member",
                cell: (row) => row.member_name,
              },
              {
                key: "inviter",
                header: "Invited by",
                cell: (row) =>
                  row.inviter_name ??
                  (row.code === "vanity" ? "vanity URL" : "unknown"),
              },
              {
                key: "code",
                header: "Code",
                cell: (row) =>
                  row.code && row.code !== "vanity" ? (
                    <Badge variant="neutral">{row.code}</Badge>
                  ) : (
                    "—"
                  ),
              },
              {
                key: "flags",
                header: "Flags",
                cell: (row) => (
                  <span className="d-flex flex-wrap gap-2">
                    {!row.rejoin ? (
                      <Badge variant="success">First join</Badge>
                    ) : (
                      <Badge variant="warning">Rejoin</Badge>
                    )}
                    {row.left_at ? (
                      <Badge variant="danger">Left</Badge>
                    ) : null}
                  </span>
                ),
              },
              {
                key: "when",
                header: "Joined",
                className: "text-nowrap",
                cell: (row) => formatDateTime(row.joined_at, lang),
              },
            ]}
            rows={filteredRecent}
            rowKey={(row) =>
              `${row.joined_at}-${row.member_name}-${row.code ?? ""}`
            }
            emptyMessage="No matching joins."
            search={recentSearch}
            onSearchChange={setRecentSearch}
            searchPlaceholder="Search joins…"
            page={recentPage}
            pageSize={10}
            onPageChange={setRecentPage}
            toolbar={
              <div className="d-flex align-items-center gap-2 small text-body-secondary">
                <Icon icon={cilPeople} />
                {filteredRecent.length} in range
              </div>
            }
          />
        )}
      </SectionCard>
    </div>
  );
}
