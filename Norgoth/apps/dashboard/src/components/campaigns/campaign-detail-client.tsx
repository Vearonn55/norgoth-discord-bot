"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CAlert } from "@coreui/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { formatDict, useLocaleDict } from "@/lib/locale-dict";

type CampaignStatus =
  | "draft"
  | "scheduled"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "stopped";

type PlatformResult = {
  sent_count?: number;
  failed_count?: number;
  retry_count?: number;
  permanent_failed_count?: number;
};

type RecipientResult = {
  user_id: string;
  user_name: string;
  status: "sent" | "failed";
  attempts: number;
  error?: string | null;
  at?: string;
};

type Campaign = {
  id: string;
  title: string;
  message: string;
  audience_count: number;
  status: CampaignStatus;
  sent_count: number;
  failed_count: number;
  retry_count?: number;
  permanent_failed_count?: number;
  delivery_target?: "channel" | "dm";
  recipient_results?: RecipientResult[];
  platform_results?: Record<string, PlatformResult>;
  platforms?: string[];
  executed_at?: string | null;
  created_at: string;
  updated_at: string;
};

type CampaignActivity = {
  id: string;
  campaign_id: string;
  campaign_title: string;
  type: string;
  message: string;
  sent_count: number;
  failed_count: number;
  audience_count: number;
  created_at: string;
};


export default function CampaignDetailClient() {
  const params = useParams();
  const router = useRouter();

  const lang = String(params?.lang || "en");
  const campaignId = String(params?.slug || "");
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [activities, setActivities] = useState<CampaignActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const dict = useLocaleDict();
  const t = dict.campaignDetail;

  const isExecuting =
    campaign?.status === "queued" || campaign?.status === "running";

  const processedCount = useMemo(() => {
    if (!campaign) return 0;
    return Number(campaign.sent_count || 0) + Number(campaign.failed_count || 0);
  }, [campaign]);

  const progressPercent = useMemo(() => {
    if (!campaign || campaign.audience_count <= 0) return 0;

    return Math.min(
      100,
      Math.round((processedCount / campaign.audience_count) * 100),
    );
  }, [campaign, processedCount]);

  const platformRows = useMemo(() => {
    if (!campaign?.platform_results) return [];

    return Object.entries(campaign.platform_results).map(([platform, result]) => {
      const sent = Number(result?.sent_count || 0);
      const failed = Number(result?.failed_count || 0);
      const retry = Number(result?.retry_count || 0);
      const permanentFailed = Number(result?.permanent_failed_count || 0);
      const total = sent + failed;
      const successRate = total > 0 ? Math.round((sent / total) * 100) : 0;

      return {
        platform,
        sent,
        failed,
        retry,
        permanentFailed,
        total,
        successRate,
      };
    });
  }, [campaign]);

  const deliveryChartData = useMemo(() => {
    if (!campaign) return [];

    return [
      {
        name: t.chartSent,
        value: Number(campaign.sent_count || 0),
        color: "#6ee7b7",
      },
      {
        name: t.chartFailed,
        value: Number(campaign.failed_count || 0),
        color: "#fca5a5",
      },
      {
        name: t.chartRetries,
        value: Number(campaign.retry_count || 0),
        color: "#fcd34d",
      },
      {
        name: t.chartPermanent,
        value: Number(campaign.permanent_failed_count || 0),
        color: "#f87171",
      },
    ];
  }, [campaign, t.chartSent, t.chartFailed, t.chartRetries, t.chartPermanent]);

  const hasDeliveryData = deliveryChartData.some((entry) => entry.value > 0);

  const retryCount = Number(campaign?.retry_count || 0);
  const permanentFailedCount = Number(campaign?.permanent_failed_count || 0);
  const hasPermanentFailures =
    (campaign?.status === "completed" || campaign?.status === "failed") &&
    permanentFailedCount > 0;
  const recipientResults = campaign?.recipient_results ?? [];

  const loadActivity = useCallback(async () => {
    if (!campaignId) return;

    try {
      const response = await fetch(
        apiUrl(`/campaigns/${campaignId}/activity`),
        {
          method: "GET",
          cache: "no-store",
        },
      );

      if (!response.ok) {
        setActivities([]);
        return;
      }

      const data = await response.json();
      setActivities(Array.isArray(data) ? data : []);
    } catch {
      setActivities([]);
    }
  }, [campaignId]);

  const loadCampaign = useCallback(async () => {
    if (!campaignId) return;

    try {
      setError(null);

      const response = await fetch(apiUrl(`/campaigns/${campaignId}`), {
        method: "GET",
        cache: "no-store",
      });

      if (response.status === 404) {
        setCampaign(null);
        setActivities([]);
        setLoading(false);
        return;
      }

      if (!response.ok) {
        setError(t.backendError);
        setLoading(false);
        return;
      }

      const data = await response.json();
      setCampaign(data);
      await loadActivity();
    } catch {
      setError(t.backendError);
    } finally {
      setLoading(false);
    }
  }, [campaignId, loadActivity, t.backendError]);

  useEffect(() => {
    loadCampaign();

    const interval = window.setInterval(() => {
      loadCampaign();
    }, 5000);

    return () => window.clearInterval(interval);
  }, [loadCampaign]);

  async function runAction(action: "start" | "stop" | "complete" | "execute") {
    if (!campaignId || actionLoading) return;

    try {
      setActionLoading(action);
      setError(null);

      const response = await fetch(
        apiUrl(`/campaigns/${campaignId}/${action}`),
        { method: "POST" },
      );

      if (response.status === 404) {
        setCampaign(null);
        setActivities([]);
        return;
      }

      if (!response.ok) {
        setError(t.backendError);
        return;
      }

      const data = await response.json();
      setCampaign(data);
      await loadActivity();

      window.setTimeout(() => {
        loadCampaign();
      }, 700);
    } catch {
      setError(t.backendError);
    } finally {
      setActionLoading(null);
    }
  }

  function requestDelete() {
    if (!campaignId || actionLoading || isExecuting) return;
    setConfirmDelete(true);
  }

  async function performDelete() {
    if (!campaignId) return;

    try {
      setActionLoading("delete");

      const response = await fetch(apiUrl(`/campaigns/${campaignId}`), {
        method: "DELETE",
      });

      if (response.status === 404) {
        router.push(`/${lang}/campaigns`);
        return;
      }

      if (!response.ok) {
        setError(t.backendError);
        return;
      }

      setConfirmDelete(false);
      router.push(`/${lang}/campaigns`);
    } catch {
      setError(t.backendError);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="d-flex flex-column gap-4">
      <ConfirmDialog
        visible={confirmDelete}
        title={t.deleteTitle}
        message={t.deleteMessage}
        confirmLabel={t.delete}
        cancelLabel={t.cancel}
        destructive
        busy={actionLoading === "delete"}
        onConfirm={performDelete}
        onCancel={() => setConfirmDelete(false)}
      />

      <div className="d-flex align-items-center justify-content-between gap-3">
        <Button asChild variant="secondary" size="sm">
          <Link href={`/${lang}/campaigns`}>
            ← {t.campaigns}
          </Link>
        </Button>

        <Button asChild variant="secondary" size="sm">
          <Link
            href={
              lang === "tr"
                ? `/en/campaigns/${campaignId}`
                : `/tr/campaigns/${campaignId}`
            }
          >
            {lang === "tr" ? "EN" : "TR"}
          </Link>
        </Button>
      </div>

      <section className="mx-auto w-100" style={{ maxWidth: 1152 }}>
              {loading ? (
                <div className="border rounded p-4 small text-body-secondary">
                  {t.loading}
                </div>
              ) : !campaign ? (
                <div className="border rounded p-4 small text-body-secondary">
                  <p>{t.notFound}</p>
                  <Button asChild variant="secondary" size="sm" className="mt-3">
                    <Link href={`/${lang}/campaigns`}>{t.back}</Link>
                  </Button>
                </div>
              ) : (
                <>
                  <div className="mb-4 d-flex align-items-start justify-content-between gap-3">
                    <div>
                      <Button asChild variant="secondary" size="sm" className="mb-3">
                        <Link href={`/${lang}/campaigns`}>{t.back}</Link>
                      </Button>

                      <h1 className="fs-3 fw-semibold">
                        {campaign.title}
                      </h1>
                      <p className="mt-2 small text-body-secondary">{t.subtitle}</p>
                    </div>

                    <div className="d-flex flex-wrap align-items-center justify-content-end gap-2">
                      <Button
                        asChild
                        variant="secondary"
                        size="sm"
                        className={isExecuting ? "pe-none opacity-50" : undefined}
                      >
                        <Link href={`/${lang}/campaigns/${campaign.id}/edit`}>
                          {t.edit}
                        </Link>
                      </Button>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => runAction("start")}
                        disabled={Boolean(actionLoading) || isExecuting}
                      >
                        {actionLoading === "start" ? "..." : t.start}
                      </Button>

                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => runAction("execute")}
                        disabled={Boolean(actionLoading) || isExecuting}
                      >
                        {actionLoading === "execute" ? "..." : t.execute}
                      </Button>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => runAction("stop")}
                        disabled={Boolean(actionLoading) || !isExecuting}
                        className="text-warning border-warning"
                      >
                        {actionLoading === "stop" ? "..." : t.stop}
                      </Button>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => runAction("complete")}
                        disabled={Boolean(actionLoading) || isExecuting}
                        className="text-success border-success"
                      >
                        {actionLoading === "complete" ? "..." : t.complete}
                      </Button>

                      <Button
                        variant="danger"
                        size="sm"
                        onClick={requestDelete}
                        disabled={Boolean(actionLoading) || isExecuting}
                      >
                        {actionLoading === "delete" ? "..." : t.delete}
                      </Button>
                    </div>
                  </div>

                  {error ? (
                    <CAlert color="danger" className="mb-3">
                      {error}
                    </CAlert>
                  ) : null}

                  {hasPermanentFailures ? (
                    <CAlert color="danger" className="mb-4">
                      {formatDict(t.permanentFailuresAlert, { count: permanentFailedCount })}
                    </CAlert>
                  ) : null}

                  <div className="row g-3 mb-4">
                    <MetricCard label={t.status} value={campaign.status} />
                    <MetricCard
                      label={t.audience}
                      value={campaign.audience_count}
                    />
                    <MetricCard label={t.sent} value={campaign.sent_count} />
                    <MetricCard
                      label={t.failed}
                      value={campaign.failed_count}
                      danger
                    />
                    <MetricCard label={t.retries} value={retryCount} />
                    <MetricCard
                      label={t.permanentFailed}
                      value={permanentFailedCount}
                      danger={permanentFailedCount > 0}
                    />
                  </div>

                  <div className="mb-4 border rounded p-4">
                    <div className="d-flex align-items-center justify-content-between small mb-3">
                      <span>{t.progress}</span>
                      <span >
                        {processedCount} / {campaign.audience_count} ·{" "}
                        {progressPercent}%
                      </span>
                    </div>

                    <div className="progress" style={{ height: 8 }}>
                      <div
                        className={`progress-bar ${hasPermanentFailures ? "bg-danger" : "bg-primary"
                          }`}
                        style={{ width: `${progressPercent}%` }}
                      />
                    </div>

                    {isExecuting ? (
                      <p className="mt-3 small text-success">
                        {t.liveExecution}
                      </p>
                    ) : null}
                  </div>

                  <div className="mb-4 border rounded p-4">
                    <h2 className="mb-3 small fw-semibold ">
                      {t.platformBreakdown}
                    </h2>
                    <p className="mb-4 small text-body-secondary">
                      {t.platformSubtitle}
                    </p>

                    {platformRows.length === 0 ? (
                      <div className="border rounded p-4 small text-body-secondary">
                        {t.noPlatformData}
                      </div>
                    ) : (
                      <div className="row g-3">
                        {platformRows.map((row) => (
                          <PlatformCard
                            key={row.platform}
                            platform={row.platform}
                            sent={row.sent}
                            failed={row.failed}
                            retry={row.retry}
                            permanentFailed={row.permanentFailed}
                            successRate={row.successRate}
                          />
                        ))}
                      </div>
                    )}
                  </div>

                  {campaign.delivery_target === "dm" ? (
                    <div className="mb-4 border rounded p-4">
                      <h2 className="mb-1 small fw-semibold ">
                        {t.dmResultsTitle}
                      </h2>
                      <p className="mb-4 small text-body-secondary">
                        {t.dmResultsSubtitle}
                      </p>

                      {recipientResults.length === 0 ? (
                        <div className="border rounded p-4 small text-body-secondary">
                          {t.noRecipientResults}
                        </div>
                      ) : (
                        <div
                          className="overflow-auto border rounded"
                          style={{ maxHeight: 360 }}
                        >
                          {recipientResults.map((result) => (
                            <div
                              key={`${result.user_id}-${result.at ?? ""}`}
                              className="row g-2 align-items-center px-3 py-2 small"
                            >
                              <div className="col-4 text-truncate">
                                {result.user_name || result.user_id}
                              </div>
                              <div className="col-2">
                                <Badge
                                  variant={
                                    result.status === "sent"
                                      ? "success"
                                      : "danger"
                                  }
                                >
                                  {result.status}
                                </Badge>
                              </div>
                              <div className="col-2 text-body-secondary">
                                {result.attempts}{" "}
                                {result.attempts === 1 ? t.attemptOne : t.attemptMany}
                              </div>
                              <div className="col-4 text-truncate small text-body-secondary">
                                {result.error || "—"}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null}

                  <div className="mb-4 border rounded p-4">
                    <h2 className="mb-1 small fw-semibold ">
                      {t.deliveryAnalytics}
                    </h2>
                    <p className="mb-4 small text-body-secondary">
                      {t.deliveryAnalyticsSubtitle}
                    </p>

                    {!hasDeliveryData ? (
                      <div className="border rounded p-4 small text-body-secondary">
                        {t.noDeliveryData}
                      </div>
                    ) : (
                      <div style={{ height: 256 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={deliveryChartData}>
                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="#27272a"
                            />
                            <XAxis
                              dataKey="name"
                              stroke="#71717a"
                              fontSize={12}
                            />
                            <YAxis
                              allowDecimals={false}
                              stroke="#71717a"
                              fontSize={12}
                            />
                            <Tooltip
                              cursor={{ fill: "rgba(255,255,255,0.04)" }}
                              contentStyle={{
                                backgroundColor: "#09090b",
                                border: "1px solid #27272a",
                                borderRadius: 12,
                                color: "#fafafa",
                              }}
                            />
                            <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                              {deliveryChartData.map((entry) => (
                                <Cell key={entry.name} fill={entry.color} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>

                  <div className="mb-4 border rounded p-4">
                    <h2 className="mb-3 small fw-semibold ">
                      {t.retrySummary}
                    </h2>

                    <div className="row g-3">
                      <InfoBox
                        label={t.retries}
                        value={String(retryCount)}
                        helper={t.retriesHelper}
                      />
                      <InfoBox
                        label={t.permanentFailed}
                        value={String(permanentFailedCount)}
                        danger={permanentFailedCount > 0}
                        helper={t.permanentHelper}
                      />
                      <InfoBox
                        label={t.result}
                        value={
                          hasPermanentFailures
                            ? "completed_with_failures"
                            : campaign.status
                        }
                        danger={hasPermanentFailures}
                        helper={
                          hasPermanentFailures
                            ? t.resultWithFailuresHelper
                            : t.resultCleanHelper
                        }
                      />
                    </div>
                  </div>

                  <div className="row g-4">
                    <div className="col-12 col-md-6">
                      <div className="border rounded p-4 h-100">
                        <h2 className="mb-3 small fw-semibold ">
                          {t.message}
                        </h2>
                        <p className="text-break small">
                          {campaign.message || "—"}
                        </p>
                      </div>
                    </div>

                    <div className="col-12 col-md-6">
                      <div className="border rounded p-4 h-100">
                        <h2 className="mb-3 small fw-semibold ">
                          {t.timestamps}
                        </h2>

                        <div className="d-flex flex-column gap-3 small">
                          <InfoRow
                            label={t.createdAt}
                            value={formatDateTime(campaign.created_at, lang)}
                          />
                          <InfoRow
                            label={t.updatedAt}
                            value={formatDateTime(campaign.updated_at, lang)}
                          />
                          <InfoRow
                            label={t.executedAt}
                            value={formatDateTime(campaign.executed_at, lang)}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 overflow-hidden border rounded">
                    <div className="border-bottom px-4 py-3">
                      <h2 className="small fw-semibold ">
                        {t.activityLog}
                      </h2>
                      <p className="mt-1 small text-body-secondary">
                        {t.activitySubtitle}
                      </p>
                    </div>

                    {activities.length === 0 ? (
                      <div className="px-4 py-4 small text-body-secondary">
                        {t.noActivity}
                      </div>
                    ) : (
                      <div className="overflow-auto" style={{ maxHeight: 520 }}>
                        {activities.map((activity) => (
                          <div
                            key={activity.id}
                            className="row g-3 px-3 py-3 small"
                          >
                            <div className="col-3">
                              <Badge variant="neutral">{activity.type}</Badge>
                            </div>

                            <div className="col-5">
                              <p className="mb-0">{activity.message}</p>
                              <p className="mt-1 mb-0 small text-body-secondary">
                                {formatDateTime(activity.created_at, lang)}
                              </p>
                            </div>

                            <div className="col-2">
                              {formatDict(t.activitySent, { count: activity.sent_count })}
                            </div>

                            <div className="col-2 text-danger">
                              {formatDict(t.activityFailed, { count: activity.failed_count })}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
      </section>
    </div>
  );
}

function PlatformCard({
  platform,
  sent,
  failed,
  retry,
  permanentFailed,
  successRate,
}: {
  platform: string;
  sent: number;
  failed: number;
  retry: number;
  permanentFailed: number;
  successRate: number;
}) {
  const dict = useLocaleDict();
  const t = dict.campaignDetail;
  return (
    <div className="border rounded p-4">
      <div className="mb-3 d-flex align-items-center justify-content-between gap-3">
        <div>
          <p className="small fw-semibold text-uppercase mb-0">
            {platform}
          </p>
          <p className="mt-1 mb-0 small text-body-secondary">
            {formatDict(t.successRate, { rate: successRate })}
          </p>
        </div>

        <Badge variant={permanentFailed > 0 ? "danger" : "success"}>
          {permanentFailed > 0 ? t.issues : t.clean}
        </Badge>
      </div>

      <div className="mb-3 progress" style={{ height: 8 }}>
        <div
          className={`progress-bar ${permanentFailed > 0 ? "bg-danger" : "bg-success"
            }`}
          style={{ width: `${successRate}%` }}
        />
      </div>

      <div className="row g-3 small">
        <SmallStat label={t.sent} value={sent} />
        <SmallStat label={t.failed} value={failed} danger={failed > 0} />
        <SmallStat label={t.retries} value={retry} />
        <SmallStat
          label={t.chartPermanent}
          value={permanentFailed}
          danger={permanentFailed > 0}
        />
      </div>
    </div>
  );
}

function SmallStat({
  label,
  value,
  danger,
}: {
  label: string;
  value: number;
  danger?: boolean;
}) {
  return (
    <div className="border rounded p-3">
      <p className="small text-body-secondary">{label}</p>
      <p
        className={`mt-1 fs-5 fw-semibold ${danger ? "text-danger" : ""
          }`}
      >
        {value}
      </p>
    </div>
  );
}

function MetricCard({
  label,
  value,
  danger,
}: {
  label: string;
  value: string | number;
  danger?: boolean;
}) {
  return (
    <div className="border rounded p-4">
      <p className="small text-body-secondary">{label}</p>
      <p
        className={`mt-3 fs-3 fw-semibold ${danger ? "text-danger" : ""
          }`}
      >
        {value}
      </p>
    </div>
  );
}

function InfoBox({
  label,
  value,
  helper,
  danger,
}: {
  label: string;
  value: string;
  helper: string;
  danger?: boolean;
}) {
  return (
    <div className="border rounded p-3">
      <p className="small text-body-secondary">{label}</p>
      <p
        className={`mt-2 fs-4 fw-semibold ${danger ? "text-danger" : ""
          }`}
      >
        {value}
      </p>
      <p className="mt-2 small text-body-secondary">{helper}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="d-flex align-items-start justify-content-between gap-3 border-bottom pb-3">
      <span className="text-body-secondary">{label}</span>
      <span className="text-end">{value}</span>
    </div>
  );
}
