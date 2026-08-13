"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { cilClock, cilHeart, cilReload } from "@coreui/icons";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import en from "@/dictionaries/en.json";
import tr from "@/dictionaries/tr.json";

type WorkerState = "online" | "offline" | "unknown" | "degraded" | "paused" | "checking";

type WorkerHealthItem = {
  type: string;
  display_name: string;
  compose_service: string;
  state: WorkerState;
  online: boolean;
  last_heartbeat: string | null;
  heartbeat_age_seconds: number | null;
  expected_instances: number;
  observed_instances: number;
  required: boolean;
};

type WorkersHealthResponse = {
  workers: WorkerHealthItem[];
  overall_state: WorkerState;
  redis_available: boolean;
  checked_at: string;
};

const COPY = {
  en: en.workerHealth,
  tr: tr.workerHealth,
} as const;

function stateTone(state: WorkerState): "success" | "danger" | "warning" | "info" {
  if (state === "online") return "success";
  if (state === "offline") return "danger";
  if (state === "degraded" || state === "paused") return "warning";
  return "info";
}

function stateLabel(state: WorkerState, copy: (typeof COPY)["en"]): string {
  switch (state) {
    case "online":
      return copy.stateOnline;
    case "offline":
      return copy.stateOffline;
    case "degraded":
      return copy.stateDegraded;
    case "paused":
      return copy.statePaused;
    case "unknown":
      return copy.stateUnknown;
    default:
      return copy.stateChecking;
  }
}

export function WorkerHealthPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const copy = COPY[lang === "tr" ? "tr" : "en"];
  const [health, setHealth] = useState<WorkersHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | WorkerState>("all");

  const loadWorkerHealth = useCallback(async () => {
    try {
      const response = await fetch(apiUrl(`/observability/workers/health`), {
        cache: "no-store",
        credentials: "include",
      });

      if (!response.ok) {
        setHealth(null);
        return;
      }

      const data: WorkersHealthResponse = await response.json();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkerHealth();
    const interval = window.setInterval(() => {
      loadWorkerHealth();
    }, 15000);
    return () => window.clearInterval(interval);
  }, [loadWorkerHealth]);

  const overallState: WorkerState = loading
    ? "checking"
    : health?.overall_state ?? "unknown";
  const overallTone = stateTone(overallState);

  const workers = useMemo(() => {
    const list = health?.workers ?? [];
    if (filter === "all") return list;
    return list.filter((item) => item.state === filter);
  }, [filter, health?.workers]);

  const onlineCount = health?.workers.filter((w) => w.state === "online").length ?? 0;
  const totalCount = health?.workers.length ?? 0;

  return (
    <Card>
      <div className="mb-4 d-flex flex-wrap align-items-center justify-content-between gap-3">
        <div className="d-flex align-items-start gap-3">
          <Icon icon={cilHeart} size="lg" className="text-body-secondary mt-1" />
          <div>
            <h2 className="h5 mb-0 fw-semibold">{copy.title}</h2>
            <p className="mt-1 mb-0 small text-body-secondary">{copy.description}</p>
          </div>
        </div>

        <div className="d-flex align-items-center gap-3">
          <div className="d-flex align-items-center gap-2" aria-live="polite">
            <span
              className={`rounded-circle d-inline-block ${
                overallTone === "success"
                  ? "bg-success"
                  : overallTone === "danger"
                    ? "bg-danger"
                    : overallTone === "warning"
                      ? "bg-warning"
                      : "bg-info"
              }`}
              style={{ width: 8, height: 8 }}
              aria-hidden
            />
            <span className="small fw-semibold">{stateLabel(overallState, copy)}</span>
            {!loading && health ? (
              <span className="small text-body-secondary">
                ({onlineCount}/{totalCount} {copy.activeInstances})
              </span>
            ) : null}
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => {
              setLoading(true);
              void loadWorkerHealth();
            }}
            aria-label={copy.refresh}
          >
            <Icon icon={cilReload} size="sm" className="me-1" />
            {copy.refresh}
          </Button>
        </div>
      </div>

      <div className="mb-3 d-flex flex-wrap gap-2" role="group" aria-label={copy.filterLabel}>
        {(
          [
            ["all", copy.filterAll],
            ["online", copy.stateOnline],
            ["paused", copy.statePaused],
            ["degraded", copy.stateDegraded],
            ["offline", copy.stateOffline],
            ["unknown", copy.stateUnknown],
          ] as const
        ).map(([value, label]) => (
          <Button
            key={value}
            type="button"
            size="sm"
            variant={filter === value ? "primary" : "secondary"}
            onClick={() => setFilter(value)}
            aria-pressed={filter === value}
          >
            {label}
          </Button>
        ))}
      </div>

      <div className="table-responsive">
        <table className="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th scope="col">{copy.colWorker}</th>
              <th scope="col">{copy.colStatus}</th>
              <th scope="col">{copy.colInstances}</th>
              <th scope="col">{copy.colLastHeartbeat}</th>
              <th scope="col">{copy.colAge}</th>
            </tr>
          </thead>
          <tbody>
            {loading && !health ? (
              <tr>
                <td colSpan={5} className="text-body-secondary">
                  {copy.loading}
                </td>
              </tr>
            ) : null}
            {!loading && !health ? (
              <tr>
                <td colSpan={5} className="text-danger">
                  {copy.unavailable}
                </td>
              </tr>
            ) : null}
            {workers.map((worker) => {
              const tone = stateTone(worker.state);
              return (
                <tr key={worker.type}>
                  <td>
                    <div className="fw-semibold">{worker.display_name}</div>
                    <div className="small text-body-secondary">
                      {worker.compose_service} · {worker.type}
                    </div>
                  </td>
                  <td>
                    <span
                      className={
                        tone === "success"
                          ? "text-success"
                          : tone === "danger"
                            ? "text-danger"
                            : tone === "warning"
                              ? "text-warning"
                              : "text-info"
                      }
                    >
                      {stateLabel(worker.state, copy)}
                    </span>
                  </td>
                  <td>
                    {worker.observed_instances}/{worker.expected_instances}
                  </td>
                  <td>{formatDateTime(worker.last_heartbeat, lang)}</td>
                  <td>
                    {worker.heartbeat_age_seconds == null
                      ? "—"
                      : `${worker.heartbeat_age_seconds}s`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 border rounded px-3 py-3 small text-body-secondary d-flex align-items-center gap-2">
        <Icon icon={cilClock} size="sm" />
        <span>
          {copy.checkedAt}: {formatDateTime(health?.checked_at ?? null, lang)}
          {health && !health.redis_available ? ` · ${copy.redisUnavailable}` : ""}
        </span>
      </div>
    </Card>
  );
}
