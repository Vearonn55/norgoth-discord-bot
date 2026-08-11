"use client";

import { Button } from "@/components/ui/button";

export type MessageSourceMode = "text" | "embed";

type MessageSourceToggleProps = {
  value: MessageSourceMode;
  onChange: (next: MessageSourceMode) => void;
  /** Accessible name for the control group. */
  ariaLabel?: string;
  className?: string;
};

/**
 * Segmented Text ↔ Embed control shared by Welcome, Tickets, and Role Menus.
 */
export function MessageSourceToggle({
  value,
  onChange,
  ariaLabel = "Message type",
  className = "",
}: MessageSourceToggleProps) {
  return (
    <div
      className={`btn-group btn-group-sm ${className}`.trim()}
      role="group"
      aria-label={ariaLabel}
    >
      <Button
        variant={value === "text" ? "primary" : "secondary"}
        size="sm"
        onClick={() => onChange("text")}
      >
        Plain text
      </Button>
      <Button
        variant={value === "embed" ? "primary" : "secondary"}
        size="sm"
        onClick={() => onChange("embed")}
      >
        Embed draft
      </Button>
    </div>
  );
}
