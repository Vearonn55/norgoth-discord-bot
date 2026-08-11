import type { ReactNode } from "react";

export type MetricAccent =
  | "primary"
  | "danger"
  | "warning"
  | "success"
  | "info";

type MetricWidgetProps = {
  label: string;
  value: ReactNode;
  helper?: ReactNode;
  accent?: MetricAccent;
  icon?: ReactNode;
  className?: string;
};

export function MetricWidget({
  label,
  value,
  helper,
  accent = "primary",
  icon,
  className,
}: MetricWidgetProps) {
  const classes = ["norgoth-metric-widget", "h-100", className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes} data-accent={accent}>
      <div className="d-flex align-items-start justify-content-between gap-3">
        <div className="min-w-0">
          <div className="norgoth-metric-label text-uppercase">{label}</div>
          <div className="norgoth-metric-value mt-2 fs-4 fw-semibold text-truncate">
            {value}
          </div>
        </div>
        {icon ? <div className="norgoth-metric-icon flex-shrink-0">{icon}</div> : null}
      </div>
      {helper ? (
        <div className="mt-2 small text-body-secondary">{helper}</div>
      ) : null}
    </div>
  );
}
