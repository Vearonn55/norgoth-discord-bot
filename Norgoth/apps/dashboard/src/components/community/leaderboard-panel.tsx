"use client";

import { useEffect, useMemo } from "react";
import { CAlert, CSpinner } from "@coreui/react";
import { cilBarChart, cilStar } from "@coreui/icons";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icon";
import { PageHeader } from "@/components/layout/page-header";
import {
  SegmentedControl,
  SegmentedPanel,
} from "@/components/ui/segmented-control";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";
import { useFirstGuild } from "@/lib/use-first-guild";
import {
  useLevelingStore,
  type LeaderboardMetric,
} from "@/stores/leveling-store";

function isMetricId(value: string | null): value is LeaderboardMetric {
  return value === "text" || value === "voice" || value === "net_upvotes";
}

export function LeaderboardPanel() {
  const dict = useLocaleDict();
  const d = dict.leaderboardPage;
  const params = useParams();
  const searchParams = useSearchParams();
  const lang = typeof params?.lang === "string" ? params.lang : "en";
  const { guildId, loading, error, reload } = useFirstGuild();

  const leaderboard = useLevelingStore((s) => s.leaderboard);
  const leaderboardMetric = useLevelingStore((s) => s.leaderboardMetric);
  const leaderboardSearch = useLevelingStore((s) => s.leaderboardSearch);
  const leaderboardPage = useLevelingStore((s) => s.leaderboardPage);
  const setLeaderboardSearch = useLevelingStore((s) => s.setLeaderboardSearch);
  const setLeaderboardPage = useLevelingStore((s) => s.setLeaderboardPage);
  const setLeaderboardMetric = useLevelingStore((s) => s.setLeaderboardMetric);
  const loadLeaderboard = useLevelingStore((s) => s.loadLeaderboard);
  const feedback = useLevelingStore((s) => s.feedback);
  const feedbackIsError = useLevelingStore((s) => s.feedbackIsError);

  const metricTabs = useMemo(
    () =>
      [
        { id: "text" as const, label: d.tabText },
        { id: "voice" as const, label: d.tabVoice },
        { id: "net_upvotes" as const, label: d.tabNetUpvotes },
      ] as const,
    [d.tabText, d.tabVoice, d.tabNetUpvotes]
  );

  // Deep-link from global search: ?metric=text|voice|net_upvotes
  useEffect(() => {
    const metric = searchParams.get("metric");
    if (isMetricId(metric) && metric !== leaderboardMetric) {
      setLeaderboardMetric(metric);
    }
  }, [leaderboardMetric, searchParams, setLeaderboardMetric]);

  useEffect(() => {
    if (!guildId) return;
    void loadLeaderboard(guildId, leaderboardMetric);
  }, [guildId, leaderboardMetric, loadLeaderboard]);

  const filteredLeaderboard = useMemo(() => {
    const query = leaderboardSearch.trim().toLowerCase();
    if (!query) return leaderboard;
    return leaderboard.filter((entry) =>
      entry.name.toLowerCase().includes(query)
    );
  }, [leaderboard, leaderboardSearch]);

  const onMetricChange = (metric: LeaderboardMetric) => {
    setLeaderboardMetric(metric);
  };

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

  const isNet = leaderboardMetric === "net_upvotes";
  const headerTitle = isNet
    ? d.tabNetUpvotes
    : leaderboardMetric === "voice"
      ? d.tabVoice
      : d.tabText;

  const emptyMessage = isNet
    ? d.emptyNet
    : leaderboardMetric === "voice"
      ? d.emptyVoice
      : d.emptyText;

  return (
    <div className="d-flex flex-column gap-4">
      <PageHeader
        title={d.title}
        icon={<Icon icon={cilBarChart} size="xl" />}
        category="leveling"
        description={d.description}
        infoKey="leaderboard"
      />

      <SegmentedControl
        options={[...metricTabs]}
        value={leaderboardMetric}
        onChange={onMetricChange}
        ariaLabel={d.metricAria}
      />

      <SegmentedPanel>
        <Card>
          <div className="d-flex flex-column gap-3">
            <div className="d-flex align-items-center justify-content-between gap-3 flex-wrap">
              <div className="d-flex align-items-start gap-3">
                <Icon
                  icon={cilStar}
                  size="lg"
                  className="text-body-secondary mt-1"
                />
                <div>
                  <h2 className="h5 mb-0 fw-semibold">
                    {formatDict(d.rankingsTitle, { metric: headerTitle })}
                  </h2>
                  <p className="mt-1 mb-0 small text-body-secondary">
                    {isNet ? (
                      <>
                        {d.netDescBefore}{" "}
                        <Link href={`/${lang}/community/feed-channels`}>
                          {d.netDescLink}
                        </Link>
                        {d.netDescAfter}
                      </>
                    ) : (
                      <>
                        {d.xpDescBefore}{" "}
                        <Link href={`/${lang}/community/leveling`}>
                          {d.xpDescLink}
                        </Link>
                        {d.xpDescAfter}
                      </>
                    )}
                  </p>
                </div>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  guildId && void loadLeaderboard(guildId, leaderboardMetric)
                }
              >
                {d.refresh}
              </Button>
            </div>

            {feedback ? (
              <CAlert
                color={feedbackIsError ? "danger" : "success"}
                className="mb-0"
              >
                {feedback}
              </CAlert>
            ) : null}

            {leaderboard.length === 0 && !feedbackIsError ? (
              <CAlert color="secondary" className="mb-0">
                {emptyMessage}
              </CAlert>
            ) : leaderboard.length === 0 ? null : (
              <DataTable
                columns={
                  isNet
                    ? [
                        {
                          key: "rank",
                          header: "#",
                          cell: (row) => `#${row.rank}`,
                        },
                        {
                          key: "name",
                          header: d.colMember,
                          cell: (row) => (
                            <div className="d-flex align-items-center gap-2">
                              <LeaderboardAvatar
                                name={row.name}
                                avatarUrl={row.avatar_url}
                              />
                              <div
                                className="d-flex flex-column min-w-0"
                                style={{ maxWidth: 220 }}
                                title={`${row.name} · ${row.user_id}`}
                              >
                                <span className="text-truncate">{row.name}</span>
                                {row.username ? (
                                  <span className="text-truncate small text-body-secondary">
                                    @{row.username}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          ),
                        },
                        {
                          key: "net",
                          header: d.colNet,
                          cell: (row) =>
                            (
                              row.net_upvotes ?? row.xp ?? 0
                            ).toLocaleString(),
                        },
                        {
                          key: "up",
                          header: d.colUpvotes,
                          cell: (row) =>
                            (row.upvote_total ?? 0).toLocaleString(),
                        },
                        {
                          key: "down",
                          header: d.colDownvotes,
                          cell: (row) =>
                            (row.downvote_total ?? 0).toLocaleString(),
                        },
                        {
                          key: "posts",
                          header: d.colPosts,
                          cell: (row) =>
                            (row.post_count ?? 0).toLocaleString(),
                        },
                      ]
                    : [
                        {
                          key: "rank",
                          header: "#",
                          cell: (row) => `#${row.rank}`,
                        },
                        {
                          key: "name",
                          header: d.colMember,
                          cell: (row) => (
                            <div className="d-flex align-items-center gap-2">
                              <LeaderboardAvatar
                                name={row.name}
                                avatarUrl={row.avatar_url}
                              />
                              <div
                                className="d-flex flex-column min-w-0"
                                style={{ maxWidth: 220 }}
                                title={`${row.name} · ${row.user_id}`}
                              >
                                <span className="text-truncate">{row.name}</span>
                                {row.username ? (
                                  <span className="text-truncate small text-body-secondary">
                                    @{row.username}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          ),
                        },
                        {
                          key: "level",
                          header: d.colLevel,
                          cell: (row) => (
                            <Badge variant="info">
                              {formatDict(d.levelBadge, { level: row.level })}
                            </Badge>
                          ),
                        },
                        {
                          key: "xp",
                          header: headerTitle,
                          cell: (row) => row.xp.toLocaleString(),
                        },
                      ]
                }
                rows={filteredLeaderboard}
                rowKey={(row) => row.user_id}
                emptyMessage={d.emptyMatching}
                search={leaderboardSearch}
                onSearchChange={setLeaderboardSearch}
                searchPlaceholder={d.searchMembers}
                page={leaderboardPage}
                pageSize={10}
                onPageChange={setLeaderboardPage}
              />
            )}
          </div>
        </Card>
      </SegmentedPanel>
    </div>
  );
}

function LeaderboardAvatar({
  name,
  avatarUrl,
}: {
  name: string;
  avatarUrl?: string | null;
}) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  const size = 28;

  if (avatarUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={avatarUrl}
        alt=""
        width={size}
        height={size}
        className="rounded-circle flex-shrink-0"
        style={{ objectFit: "cover" }}
      />
    );
  }

  return (
    <span
      className="rounded-circle d-inline-flex align-items-center justify-content-center flex-shrink-0 bg-body-secondary text-body-secondary small fw-semibold"
      style={{ width: size, height: size }}
    >
      {initial}
    </span>
  );
}
