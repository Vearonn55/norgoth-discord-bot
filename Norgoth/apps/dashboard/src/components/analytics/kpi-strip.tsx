"use client";

import type { ReactNode } from "react";

export type KpiItem = {
  key: string;
  label: string;
  value: string | number;
  helper?: string;
  tone?: "default" | "success" | "warning" | "danger" | "info";
};

type KpiStripProps = {
  items: KpiItem[];
  className?: string;
};

export function KpiStrip({ items, className }: KpiStripProps) {
  return (
    <div
      className={["norgoth-kpi-strip row g-2", className]
        .filter(Boolean)
        .join(" ")}
    >
      {items.map((item) => (
        <div key={item.key} className="col-6 col-md-3">
          <div
            className="norgoth-kpi-pill h-100"
            data-tone={item.tone ?? "default"}
          >
            <div className="small text-uppercase fw-semibold text-body-secondary">
              {item.label}
            </div>
            <div className="h4 mb-0 fw-semibold text-white">{item.value}</div>
            {item.helper ? (
              <div className="small text-body-secondary mt-1">{item.helper}</div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

type KpiPillProps = {
  label: string;
  value: ReactNode;
  helper?: string;
  tone?: KpiItem["tone"];
};

export function KpiPill({ label, value, helper, tone = "default" }: KpiPillProps) {
  return (
    <div className="norgoth-kpi-pill" data-tone={tone}>
      <div className="small text-uppercase fw-semibold text-body-secondary">
        {label}
      </div>
      <div className="h4 mb-0 fw-semibold text-white">{value}</div>
      {helper ? (
        <div className="small text-body-secondary mt-1">{helper}</div>
      ) : null}
    </div>
  );
}
