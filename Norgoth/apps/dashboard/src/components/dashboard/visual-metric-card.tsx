import type { ReactNode } from "react";
import type { MetricAccent } from "@/components/ui/metric-widget";

type VisualMetricCardProps = {
  label: string;
  value: string;
  helper: string;
  tone: MetricAccent;
  progress: number;
  icon?: ReactNode;
};

export function VisualMetricCard({
  label,
  value,
  helper,
  tone,
  progress,
  icon,
}: VisualMetricCardProps) {
  const safeProgress = Math.max(0, Math.min(100, progress));

  return (
    <div className="col-12 col-md-6 col-xl-3">
      <div className="norgoth-metric-widget h-100" data-accent={tone}>
        <div className="d-flex align-items-start justify-content-between gap-3">
          <div className="min-w-0">
            <div className="small text-body-secondary text-uppercase">{label}</div>
            <div className="mt-2 fs-3 fw-semibold text-body">{value}</div>
          </div>
          {icon ? (
            <div className="flex-shrink-0 text-body-secondary opacity-75">
              {icon}
            </div>
          ) : null}
        </div>

        <div className="mt-3 progress" style={{ height: 6 }}>
          <div
            className={`progress-bar ${barClass(tone)}`}
            style={{ width: `${safeProgress}%` }}
            role="progressbar"
            aria-valuenow={safeProgress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>

        <p className="mt-2 mb-0 small text-body-secondary">{helper}</p>
      </div>
    </div>
  );
}

function barClass(tone: string) {
  if (tone === "success") return "bg-success";
  if (tone === "warning") return "bg-warning";
  if (tone === "danger") return "bg-danger";
  if (tone === "info") return "bg-info";
  if (tone === "primary") return "bg-primary";
  return "bg-secondary";
}
