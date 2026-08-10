"use client";

import { CSpinner } from "@coreui/react";
import { Switch } from "@/components/ui/switch";

type HeaderMasterToggleProps = {
  enabled: boolean;
  onChange: (checked: boolean) => void;
  loading?: boolean;
  /** Used for aria-label; optionally shown as visible text when showLabel. */
  label?: string;
  /** When false, hide the visible label span but keep accessible name. */
  showLabel?: boolean;
};

/**
 * Page-level master enable/disable switch shown on the right of the page
 * header. Keeps the authoritative feature toggle out of configuration cards.
 */
export function HeaderMasterToggle({
  enabled,
  onChange,
  loading = false,
  label,
  showLabel = true,
}: HeaderMasterToggleProps) {
  return (
    <div className="d-flex align-items-center gap-2 flex-shrink-0">
      {showLabel && label ? (
        <span className="small fw-semibold">{label}</span>
      ) : null}
      {loading ? <CSpinner size="sm" /> : null}
      <span
        className="small"
        style={{
          color: enabled ? "var(--cui-success)" : "var(--cui-secondary)",
        }}
      >
        {enabled ? "Enabled" : "Disabled"}
      </span>
      <Switch
        size="lg"
        checked={enabled}
        disabled={loading}
        onChange={onChange}
        aria-label={label ? `Toggle ${label}` : "Toggle feature"}
      />
    </div>
  );
}
