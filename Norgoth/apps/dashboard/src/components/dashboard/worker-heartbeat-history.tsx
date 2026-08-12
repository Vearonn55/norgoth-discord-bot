"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { apiUrl } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";


type WorkerHealthResponse = {
  online: boolean;
  last_heartbeat: string | null;
  checked_at: string;
};

type HeartbeatSample = {
  id: string;
  online: boolean;
  lastHeartbeat: string | null;
  checkedAt: string;
};

export function WorkerHeartbeatHistory() {
  const params = useParams();
  const lang = String(params?.lang || "en");
  const [samples, setSamples] = useState<HeartbeatSample[]>([]);
  const [loading, setLoading] = useState(true);

  async function collectSample() {
    try {
      const response = await fetch(apiUrl(`/campaigns/worker/health`), {
        cache: "no-store",
      });

      if (!response.ok) return;

      const data: WorkerHealthResponse = await response.json();

      setSamples((prev) => {
        const next = [
          {
            id: `${Date.now()}-${Math.random()}`,
            online: data.online,
            lastHeartbeat: data.last_heartbeat,
            checkedAt: data.checked_at,
          },
          ...prev,
        ];

        return next.slice(0, 12);
      });
    } catch {
      setSamples((prev) => {
        const next = [
          {
            id: `${Date.now()}-${Math.random()}`,
            online: false,
            lastHeartbeat: null,
            checkedAt: new Date().toISOString(),
          },
          ...prev,
        ];

        return next.slice(0, 12);
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    collectSample();

    const interval = window.setInterval(() => {
      collectSample();
    }, 30000);

    return () => window.clearInterval(interval);
  }, []);

  const summary = useMemo(() => {
    const onlineCount = samples.filter((sample) => sample.online).length;
    const offlineCount = samples.length - onlineCount;
    const uptime =
      samples.length > 0 ? Math.round((onlineCount / samples.length) * 100) : 0;

    return {
      onlineCount,
      offlineCount,
      uptime,
    };
  }, [samples]);

  return (
    <div className="border rounded p-4">
      <div className="mb-4 d-flex align-items-center justify-content-between gap-3">
        <div>
          <h2 className="h5 mb-0 fw-semibold">
            Worker Heartbeat History
          </h2>

          <p className="mt-1 small text-body-secondary">
            Recent heartbeat samples collected from worker health endpoint.
          </p>
        </div>

        <div className="d-flex align-items-center gap-2">
          <span
            className="rounded-circle bg-success d-inline-block"
            style={{ width: 8, height: 8 }}
          />
          <span className="small text-success">SAMPLING</span>
        </div>
      </div>

      <div className="mb-4 row g-3">
        <div className="col-12 col-md-4">
          <HistoryStat label="Samples" value={samples.length} tone="info" />
        </div>
        <div className="col-12 col-md-4">
          <HistoryStat label="Online Samples" value={summary.onlineCount} tone="success" />
        </div>
        <div className="col-12 col-md-4">
          <HistoryStat label="Uptime Window" value={`${summary.uptime}%`} tone="success" />
        </div>
      </div>

      {loading ? (
        <div className="border rounded p-4 small text-body-secondary">
          Loading heartbeat history...
        </div>
      ) : samples.length === 0 ? (
        <div className="border rounded p-4 small text-body-secondary">
          No heartbeat samples yet.
        </div>
      ) : (
        <div className="overflow-auto pe-2 norgoth-scrollbar" style={{ maxHeight: 420 }}>
          <div className="row g-3">
            {samples.map((sample) => (
              <div key={sample.id} className="col-12 col-md-6 col-xl-4">
                <HeartbeatSampleCard sample={sample} lang={lang} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HeartbeatSampleCard({
  sample,
  lang,
}: {
  sample: HeartbeatSample;
  lang: string;
}) {
  return (
    <div
      className={`rounded border p-3 h-100 ${sample.online
        ? "border-success"
        : "border-danger"
        }`}
    >
      <div className="mb-3 d-flex align-items-center justify-content-between gap-3">
        <Badge variant={sample.online ? "success" : "danger"}>
          {sample.online ? "ONLINE" : "OFFLINE"}
        </Badge>

        <span className="small text-body-secondary">
          {formatDateTime(sample.checkedAt, lang)}
        </span>
      </div>

      <div className="small text-body-secondary text-uppercase">
        Last Heartbeat
      </div>

      <div className="mt-2 text-break small">
        {formatDateTime(sample.lastHeartbeat, lang)}
      </div>
    </div>
  );
}

function HistoryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: "success" | "info";
}) {
  const valueClass = tone === "success" ? "text-success" : "text-info";

  return (
    <div className="border rounded p-3 h-100">
      <div className="small text-body-secondary text-uppercase">
        {label}
      </div>

      <div className={`mt-3 fs-4 fw-semibold ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}
