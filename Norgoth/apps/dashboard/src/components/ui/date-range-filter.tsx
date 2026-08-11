"use client";

import { useMemo, useState } from "react";
import {
  CButton,
  CButtonGroup,
  CFormInput,
  CFormLabel,
  CCol,
  CRow,
} from "@coreui/react";

export type DateRangeValue = {
  start: string;
  end: string;
};

export type DateRangePreset = "today" | "7d" | "30d" | "90d" | "custom";

type DateRangePickerProps = {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
  startLabel?: string;
  endLabel?: string;
  className?: string;
};

/** Returns YYYY-MM-DD for local date offset by `daysAgo` (0 = today). */
export function isoDateDaysAgo(daysAgo: number): string {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

export function defaultDateRange(days = 7): DateRangeValue {
  return { start: isoDateDaysAgo(days), end: isoDateDaysAgo(0) };
}

export function isInDateRange(
  isoTimestamp: string | null | undefined,
  range: DateRangeValue
): boolean {
  if (!isoTimestamp) return false;
  const day = isoTimestamp.slice(0, 10);
  if (range.start && day < range.start) return false;
  if (range.end && day > range.end) return false;
  return true;
}

export function resolveDateRangePreset(value: DateRangeValue): DateRangePreset {
  const end = isoDateDaysAgo(0);
  if (value.end !== end) return "custom";
  if (value.start === end) return "today";
  if (value.start === isoDateDaysAgo(7)) return "7d";
  if (value.start === isoDateDaysAgo(30)) return "30d";
  if (value.start === isoDateDaysAgo(90)) return "90d";
  return "custom";
}

export function dateRangeFromPreset(preset: Exclude<DateRangePreset, "custom">): DateRangeValue {
  switch (preset) {
    case "today":
      return { start: isoDateDaysAgo(0), end: isoDateDaysAgo(0) };
    case "7d":
      return defaultDateRange(7);
    case "30d":
      return defaultDateRange(30);
    case "90d":
      return defaultDateRange(90);
  }
}

const PRESETS: { id: DateRangePreset; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "7d", label: "7d" },
  { id: "30d", label: "30d" },
  { id: "90d", label: "90d" },
  { id: "custom", label: "Custom" },
];

export function DateRangePicker({
  value,
  onChange,
  startLabel = "Start date",
  endLabel = "End date",
  className,
}: DateRangePickerProps) {
  const [forceCustom, setForceCustom] = useState(false);
  const resolved = useMemo(() => resolveDateRangePreset(value), [value]);
  const active: DateRangePreset =
    forceCustom || resolved === "custom" ? "custom" : resolved;
  const showCustom = active === "custom";

  return (
    <div className={["norgoth-date-range-picker", className].filter(Boolean).join(" ")}>
      <CButtonGroup role="group" aria-label="Date range presets" className="flex-wrap">
        {PRESETS.map((preset) => (
          <CButton
            key={preset.id}
            type="button"
            color={active === preset.id ? "primary" : "secondary"}
            variant={active === preset.id ? undefined : "outline"}
            size="sm"
            onClick={() => {
              if (preset.id === "custom") {
                setForceCustom(true);
                return;
              }
              setForceCustom(false);
              onChange(dateRangeFromPreset(preset.id));
            }}
          >
            {preset.label}
          </CButton>
        ))}
      </CButtonGroup>

      {showCustom ? (
        <CRow className="g-2 align-items-end mt-2">
          <CCol xs={12} sm={6} md="auto">
            <CFormLabel className="small mb-1">{startLabel}</CFormLabel>
            <CFormInput
              type="date"
              value={value.start}
              onChange={(e) => onChange({ ...value, start: e.target.value })}
            />
          </CCol>
          <CCol xs={12} sm={6} md="auto">
            <CFormLabel className="small mb-1">{endLabel}</CFormLabel>
            <CFormInput
              type="date"
              value={value.end}
              min={value.start || undefined}
              onChange={(e) => onChange({ ...value, end: e.target.value })}
            />
          </CCol>
        </CRow>
      ) : null}
    </div>
  );
}

/** @deprecated Use DateRangePicker */
export const DateRangeFilter = DateRangePicker;
