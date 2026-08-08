"use client";

import type { ReactNode } from "react";

export type SegmentedOption<T extends string> = {
  id: T;
  label: string;
};

type SegmentedControlProps<T extends string> = {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  className?: string;
};

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div
      className={["norgoth-segmented btn-group", className]
        .filter(Boolean)
        .join(" ")}
      role="tablist"
      aria-label={ariaLabel}
    >
      {options.map((option) => {
        const active = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={[
              "btn",
              active ? "btn-primary" : "btn-outline-secondary",
            ].join(" ")}
            onClick={() => onChange(option.id)}
            onKeyDown={(e) => {
              if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
              e.preventDefault();
              const idx = options.findIndex((o) => o.id === value);
              const next =
                e.key === "ArrowRight"
                  ? options[(idx + 1) % options.length]
                  : options[(idx - 1 + options.length) % options.length];
              onChange(next.id);
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

type SegmentedPanelProps = {
  children: ReactNode;
};

export function SegmentedPanel({ children }: SegmentedPanelProps) {
  return <div role="tabpanel">{children}</div>;
}
