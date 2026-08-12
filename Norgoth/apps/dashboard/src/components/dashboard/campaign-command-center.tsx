"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  cilCalendar,
  cilCheckCircle,
  cilMediaPlay,
  cilPencil,
  cilSend,
  cilTrash,
} from "@coreui/icons";
import { CSpinner } from "@coreui/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { MetricWidget } from "@/components/ui/metric-widget";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { apiUrl } from "@/lib/api";

type CampaignStatus =
  | "draft"
  | "scheduled"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "stopped";

type Campaign = {
  id: string;
  title?: string;
  message?: string;
  status: CampaignStatus;
  audience_count?: number;
  sent_count?: number;
  failed_count?: number;
  retry_count?: number;
  permanent_failed_count?: number;
  launch_at?: string | null;
  updated_at?: string;
};

function parseCampaigns(data: unknown): Campaign[] {
  if (Array.isArray(data)) return data as Campaign[];
  if (data && typeof data === "object") {
    const record = data as { items?: unknown; campaigns?: unknown };
    if (Array.isArray(record.items)) return record.items as Campaign[];
    if (Array.isArray(record.campaigns)) return record.campaigns as Campaign[];
  }
  return [];
}

export function CampaignCommandCenter() {
  const params = useParams();
  const lang = String(params?.lang || "en");

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Campaign | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadCampaigns = useCallback(async (isInitial = false) => {
    try {
      const response = await fetch(apiUrl(`/campaigns`), {
        cache: "no-store",
      });

      if (!response.ok) {
        if (isInitial) {
          setLoadError("Could not load campaigns from the API.");
        }
        return;
      }

      const data = await response.json();
      setCampaigns(parseCampaigns(data));
      setLoadError(null);
    } catch {
      if (isInitial) {
        setLoadError("Could not reach the NorBot API.");
      }
    } finally {
      if (isInitial) setInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCampaigns(true);

    const interval = window.setInterval(() => {
      void loadCampaigns(false);
    }, 5000);

    return () => window.clearInterval(interval);
  }, [loadCampaigns]);

  const summary = useMemo(() => {
    const total = campaigns.length;
    const active = campaigns.filter((item) =>
      ["queued", "running"].includes(item.status),
    ).length;
    const scheduled = campaigns.filter(
      (item) => item.status === "scheduled",
    ).length;
    const completed = campaigns.filter(
      (item) => item.status === "completed",
    ).length;
    const failed = campaigns.reduce(
      (sum, item) => sum + Number(item.failed_count || 0),
      0,
    );
    const sent = campaigns.reduce(
      (sum, item) => sum + Number(item.sent_count || 0),
      0,
    );

    const totalProcessed = sent + failed;
    const successRate =
      totalProcessed > 0 ? Math.round((sent / totalProcessed) * 100) : 0;

    return {
      total,
      active,
      scheduled,
      completed,
      failed,
      sent,
      successRate,
    };
  }, [campaigns]);

  const activeCampaigns = campaigns
    .filter((item) => ["queued", "running"].includes(item.status))
    .slice(0, 4);

  const scheduledCampaigns = campaigns
    .filter((item) => item.status === "scheduled")
    .slice(0, 4);

  const draftCampaigns = campaigns.filter((item) => item.status === "draft");

  const latestCampaigns = campaigns.slice(0, 6);

  async function handleConfirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      const response = await fetch(apiUrl(`/campaigns/${pendingDelete.id}`), {
        method: "DELETE",
      });
      if (response.ok) {
        setCampaigns((current) =>
          current.filter((item) => item.id !== pendingDelete.id),
        );
        setPendingDelete(null);
      }
    } catch {
      //
    } finally {
      setDeleting(false);
    }
  }

  if (initialLoading) {
    return (
      <Card>
        <div
          className="d-flex flex-column align-items-center justify-content-center gap-3 py-5 text-body-secondary"
          role="status"
          aria-live="polite"
        >
          <CSpinner />
          <div className="small">Loading Command Center…</div>
        </div>
      </Card>
    );
  }

  if (loadError) {
    return (
      <Card>
        <div className="d-flex flex-column align-items-start gap-3 py-4">
          <p className="mb-0 text-body-secondary">{loadError}</p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setInitialLoading(true);
              setLoadError(null);
              void loadCampaigns(true);
            }}
          >
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="d-flex flex-column gap-4">
      <section className="row g-3">
        <div className="col-12 col-md-6 col-xl-3">
          <MetricWidget
            label="Total Campaigns"
            value={summary.total}
            accent="info"
            icon={<Icon icon={cilSend} size="lg" />}
          />
        </div>
        <div className="col-12 col-md-6 col-xl-3">
          <MetricWidget
            label="Active"
            value={summary.active}
            accent="success"
            icon={<Icon icon={cilMediaPlay} size="lg" />}
          />
        </div>
        <div className="col-12 col-md-6 col-xl-3">
          <MetricWidget
            label="Scheduled"
            value={summary.scheduled}
            accent="warning"
            icon={<Icon icon={cilCalendar} size="lg" />}
          />
        </div>
        <div className="col-12 col-md-6 col-xl-3">
          <MetricWidget
            label="Success Rate"
            value={`${summary.successRate}%`}
            helper={`${summary.sent} sent · ${summary.failed} failed`}
            accent={summary.successRate >= 90 ? "success" : "warning"}
            icon={<Icon icon={cilCheckCircle} size="lg" />}
          />
        </div>
      </section>

      <section className="row g-4">
        <div className="col-xl-8">
          <Card className="h-100">
            <div className="mb-4 d-flex align-items-start justify-content-between gap-3">
              <div className="d-flex align-items-start gap-3">
                <Icon
                  icon={cilMediaPlay}
                  size="lg"
                  className="text-body-secondary mt-1"
                />
                <div>
                  <h2 className="h5 mb-0 fw-semibold">Active Campaign Flow</h2>
                  <p className="mt-1 mb-0 small text-body-secondary">
                    Campaigns currently queued or running through the worker.
                  </p>
                </div>
              </div>

              <Button asChild variant="secondary" size="sm">
                <Link href={`/${lang}/observability/worker-health`}>
                  Worker Health
                </Link>
              </Button>
            </div>

            {activeCampaigns.length === 0 ? (
              <EmptyBox text="No active campaign execution right now." />
            ) : (
              <div className="d-flex flex-column gap-3">
                {activeCampaigns.map((campaign) => (
                  <CampaignFlowCard
                    key={campaign.id}
                    campaign={campaign}
                    lang={lang}
                  />
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="col-xl-4">
          <Card className="h-100">
            <div className="d-flex align-items-start gap-3">
              <Icon
                icon={cilSend}
                size="lg"
                className="text-body-secondary mt-1"
              />
              <div>
                <h2 className="h5 mb-0 fw-semibold">Quick Actions</h2>
                <p className="mt-1 mb-0 small text-body-secondary">
                  Common campaign operations.
                </p>
              </div>
            </div>

            <div className="mt-4 d-flex flex-column gap-2">
              <ActionLink
                href={`/${lang}/campaigns/new`}
                label="Create Campaign"
              />
              <ActionLink
                href={`/${lang}/campaigns/history`}
                label="Campaign History"
              />
              <ActionLink
                href={`/${lang}/observability/worker-health`}
                label="Worker Health"
              />
            </div>
          </Card>
        </div>
      </section>

      <section className="row g-4">
        <div className="col-12">
          <CampaignListPanel
            title="Draft Campaigns"
            description="Unsent drafts. Continue editing or delete permanently."
            campaigns={draftCampaigns}
            lang={lang}
            emptyText="No campaign drafts."
            icon={<Icon icon={cilPencil} size="lg" />}
            onDelete={(campaign) => setPendingDelete(campaign)}
          />
        </div>

        <div className="col-12 col-xl-6">
          <CampaignListPanel
            title="Scheduled Campaigns"
            description="Campaigns waiting for launch time."
            campaigns={scheduledCampaigns}
            lang={lang}
            emptyText="No scheduled campaigns."
            icon={<Icon icon={cilCalendar} size="lg" />}
          />
        </div>

        <div className="col-12 col-xl-6">
          <CampaignListPanel
            title="Latest Campaign Records"
            description="Most recent campaign records in the system."
            campaigns={latestCampaigns}
            lang={lang}
            emptyText="No campaign records yet."
            icon={<Icon icon={cilSend} size="lg" />}
          />
        </div>
      </section>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="Delete Draft?"
        message={
          <p className="mb-0 text-body-secondary">
            The draft{" "}
            <strong>{pendingDelete?.title || "Untitled Campaign"}</strong> will
            be permanently removed. This cannot be undone.
          </p>
        }
        confirmLabel="Delete Draft"
        destructive
        busy={deleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

function CampaignFlowCard({
  campaign,
  lang,
}: {
  campaign: Campaign;
  lang: string;
}) {
  const sent = Number(campaign.sent_count || 0);
  const failed = Number(campaign.failed_count || 0);
  const audience = Number(campaign.audience_count || 0);
  const processed = sent + failed;
  const progress =
    audience > 0 ? Math.min(100, Math.round((processed / audience) * 100)) : 0;

  const isRunning = campaign.status === "running";

  return (
    <article className="border rounded p-3">
      <div className="mb-3 d-flex flex-wrap align-items-start justify-content-between gap-3">
        <div className="overflow-hidden">
          <Badge variant={isRunning ? "success" : "warning"}>
            {campaign.status}
          </Badge>

          <Link
            href={`/${lang}/campaigns/${campaign.id}`}
            className="mt-2 d-block text-truncate small fw-semibold text-decoration-none"
          >
            {campaign.title || "Untitled Campaign"}
          </Link>

          <p className="mt-1 mb-0 small text-body-secondary text-truncate">
            {campaign.message || "—"}
          </p>
        </div>

        <div className="text-end small text-body-secondary">
          Progress
          <div className="mt-1 fs-5 fw-semibold text-body">{progress}%</div>
        </div>
      </div>

      <div className="progress" style={{ height: 8 }}>
        <div
          className={`progress-bar ${failed > 0 ? "bg-danger" : "bg-success"}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="row g-2 mt-3">
        <div className="col-4">
          <MiniMetric label="Sent" value={sent} tone="success" />
        </div>
        <div className="col-4">
          <MiniMetric label="Failed" value={failed} tone="danger" />
        </div>
        <div className="col-4">
          <MiniMetric label="Audience" value={audience} />
        </div>
      </div>
    </article>
  );
}

function CampaignListPanel({
  title,
  description,
  campaigns,
  lang,
  emptyText,
  icon,
  onDelete,
}: {
  title: string;
  description: string;
  campaigns: Campaign[];
  lang: string;
  emptyText: string;
  icon?: ReactNode;
  onDelete?: (campaign: Campaign) => void;
}) {
  return (
    <Card className="h-100">
      <div className="mb-4 d-flex align-items-start justify-content-between gap-3">
        <div className="d-flex align-items-start gap-3">
          {icon ? (
            <div className="flex-shrink-0 text-body-secondary mt-1">{icon}</div>
          ) : null}
          <div>
            <h2 className="h5 mb-0 fw-semibold">{title}</h2>
            <p className="mt-1 mb-0 small text-body-secondary">{description}</p>
          </div>
        </div>

        <Badge variant="neutral">{campaigns.length}</Badge>
      </div>

      {campaigns.length === 0 ? (
        <EmptyBox text={emptyText} />
      ) : (
        <div className="overflow-auto pe-2 norgoth-scrollbar" style={{ maxHeight: 420 }}>
          <div className="d-flex flex-column gap-3">
            {campaigns.map((campaign) => (
              <Card key={campaign.id} variant="interactive">
                <div className="mb-2 d-flex align-items-center justify-content-between gap-3">
                  <Link
                    href={`/${lang}/campaigns/${campaign.id}`}
                    className="text-truncate small fw-semibold text-decoration-none"
                  >
                    {campaign.title || "Untitled Campaign"}
                  </Link>

                  <div className="d-flex align-items-center gap-2 flex-shrink-0">
                    <Badge variant="neutral">{campaign.status}</Badge>
                    {onDelete ? (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => onDelete(campaign)}
                        aria-label="Delete draft"
                      >
                        <Icon icon={cilTrash} />
                      </Button>
                    ) : null}
                  </div>
                </div>

                <p className="mb-0 small text-body-secondary text-truncate">
                  {campaign.message || "—"}
                </p>
              </Card>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function MiniMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "success" | "danger";
}) {
  const valueClass =
    tone === "success"
      ? "text-success"
      : tone === "danger"
        ? "text-danger"
        : "";

  return (
    <div className="border rounded p-2">
      <div className="small text-body-secondary">{label}</div>
      <div className={`mt-1 fs-6 fw-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}

function ActionLink({ href, label }: { href: string; label: string }) {
  return (
    <Button asChild variant="secondary" className="w-100 justify-content-start">
      <Link href={href}>{label}</Link>
    </Button>
  );
}

function EmptyBox({ text }: { text: string }) {
  return (
    <div className="border rounded p-4 small text-body-secondary">{text}</div>
  );
}
