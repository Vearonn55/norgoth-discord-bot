"use client";

import { CFormRange } from "@coreui/react";
import type { CSSProperties } from "react";

type SliderProps = {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  onPointerUp?: () => void;
  disabled?: boolean;
  id?: string;
  className?: string;
  "aria-label"?: string;
};

/**
 * Shared range/slider with strong dark-theme contrast. The filled portion of
 * the track is driven by the `--norgoth-range-fill` custom property so the
 * inactive track, active track and thumb all remain clearly visible.
 * Styling lives in globals.css under `.norgoth-range`.
 */
export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  onPointerUp,
  disabled = false,
  id,
  className,
  "aria-label": ariaLabel,
}: SliderProps) {
  const range = max - min || 1;
  const pct = Math.min(100, Math.max(0, ((value - min) / range) * 100));

  return (
    <CFormRange
      id={id}
      min={min}
      max={max}
      step={step}
      value={value}
      disabled={disabled}
      aria-label={ariaLabel}
      className={["norgoth-range", className].filter(Boolean).join(" ")}
      style={{ ["--norgoth-range-fill" as string]: `${pct}%` } as CSSProperties}
      onChange={(event) => onChange(Number(event.target.value))}
      onPointerUp={onPointerUp}
      onKeyUp={(event) => {
        if (
          onPointerUp &&
          (event.key === "ArrowLeft" ||
            event.key === "ArrowRight" ||
            event.key === "Home" ||
            event.key === "End")
        ) {
          onPointerUp();
        }
      }}
    />
  );
}
