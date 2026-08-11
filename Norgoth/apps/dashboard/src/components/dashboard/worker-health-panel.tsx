"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { cilClock, cilHeart, cilCheckCircle } from "@coreui/icons";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icon";
import { MetricWidget } from "@/components/ui/metric-widget";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";

type WorkerHealthResponse = {
  online: boolean;
  last_heartbeat: string | null;
  checked_at: string;
};

export function WorkerHealthPanel() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const [health, setHealth] = useState<WorkerHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadWorkerHealth() {
    try {
      const response = await fetch(apiUrl(`/campaigns/worker/health`), {
        cache: "no-store",
      });

      if (!response.ok) {
        setHealth(null);
        return;
      }

      const data: WorkerHealthResponse = await response.json();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWorkerHealth();

    const interval = window.setInterval(() => {
      loadWorkerHealth();
    }, 15000);

    return () => window.clearInterval(interval);
  }, []);

  const state = useMemo(() => {
    if (loading) {
      return {
        label: "CHECKING",
        tone: "info" as const,
        helper: "Worker heartbeat is being checked.",
      };
    }

    if (!health?.online) {
      return {
        label: "OFFLINE",
        tone: "danger" as const,
        helper: "No recent worker heartbeat detected.",
      };
    }

    return {
      label: "ONLINE",
      tone: "success" as const,
      helper: "Worker heartbeat is active.",
    };
  }, [health, loading]);

  return (
    <Card>
      <div className="mb-4 d-flex align-items-center justify-content-between gap-3">
        <div className="d-flex align-items-start gap-3">
          <Icon icon={cilHeart} size="lg" className="text-body-secondary mt-1" />
          <div>
            <h2 className="h5 mb-0 fw-semibold">Worker Health</h2>
            <p className="mt-1 mb-0 small text-body-secondary">
              Backend worker heartbeat and runtime availability.
            </p>
          </div>
        </div>

        <div className="d-flex align-items-center gap-2">
          <span
            className={`rounded-circle d-inline-block ${
              state.tone === "success"
                ? "bg-success"
                : state.tone === "danger"
                  ? "bg-danger"
                  : "bg-info"
            }`}
            style={{ width: 8, height: 8 }}
          />

          <span
            className={`small ${
              state.tone === "success"
                ? "text-success"
                : state.tone === "danger"
                  ? "text-danger"
                  : "text-info"
            }`}
          >
            {state.label}
          </span>
        </div>
      </div>

      <div className="row g-3">
        <div className="col-12 col-md-4">
          <MetricWidget
            label="Status"
            value={state.label}
            accent={state.tone}
            icon={<Icon icon={cilCheckCircle} size="lg" />}
          />
        </div>

        <div className="col-12 col-md-4">
          <MetricWidget
            label="Last Heartbeat"
            value={formatDateTime(health?.last_heartbeat, lang)}
            accent={state.tone}
            icon={<Icon icon={cilHeart} size="lg" />}
          />
        </div>

        <div className="col-12 col-md-4">
          <MetricWidget
            label="Checked At"
            value={formatDateTime(health?.checked_at, lang)}
            accent="info"
            icon={<Icon icon={cilClock} size="lg" />}
          />
        </div>
      </div>

      <div className="mt-4 border rounded px-3 py-3 small text-body-secondary">
        {state.helper}
      </div>
    </Card>
  );
}
