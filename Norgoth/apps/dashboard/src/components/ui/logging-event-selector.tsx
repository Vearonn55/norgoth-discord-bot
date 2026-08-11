"use client";

import type { LoggingEventKey } from "@/lib/discord/logging-events";
import {
  LOGGING_EVENT_KEYS,
  LOGGING_EVENT_LABELS,
} from "@/lib/discord/logging-events";

type LoggingEventSelectorProps = {
  selected: string[];
  onChange: (keys: string[]) => void;
};

export function LoggingEventSelector({
  selected,
  onChange,
}: LoggingEventSelectorProps) {
  function toggle(key: LoggingEventKey) {
    if (selected.includes(key)) {
      onChange(selected.filter((k) => k !== key));
    } else {
      onChange([...selected, key]);
    }
  }

  return (
    <div className="norgoth-logging-event-selector row g-2">
      {LOGGING_EVENT_KEYS.map((key) => {
        const active = selected.includes(key);
        return (
          <div key={key} className="col-md-6 col-xl-4">
            <button
              type="button"
              className={[
                "btn w-100 text-start",
                active ? "btn-primary" : "btn-outline-secondary",
              ].join(" ")}
              onClick={() => toggle(key)}
              aria-pressed={active}
            >
              <div className="fw-semibold small">{LOGGING_EVENT_LABELS[key]}</div>
              <div className="small opacity-75">{key}</div>
            </button>
          </div>
        );
      })}
    </div>
  );
}
