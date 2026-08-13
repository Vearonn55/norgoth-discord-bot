"use client";

import { Button } from "@/components/ui/button";
import { useLocaleDict } from "@/lib/locale-dict";

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
  ariaLabel,
  className = "",
}: MessageSourceToggleProps) {
  const dict = useLocaleDict();
  const label = ariaLabel ?? dict.common.messageTypeAria;

  return (
    <div
      className={`btn-group btn-group-sm ${className}`.trim()}
      role="group"
      aria-label={label}
    >
      <Button
        variant={value === "text" ? "primary" : "secondary"}
        size="sm"
        onClick={() => onChange("text")}
      >
        {dict.common.plainText}
      </Button>
      <Button
        variant={value === "embed" ? "primary" : "secondary"}
        size="sm"
        onClick={() => onChange("embed")}
      >
        {dict.common.embedDraft}
      </Button>
    </div>
  );
}
